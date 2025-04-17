import multiprocessing
import os
from datetime import datetime, timedelta

import psycopg2
from prefect import flow, task
from prefect.client.schemas.schedules import IntervalSchedule
from pyspark.sql import SparkSession

# Database connection parameters from environment variables
DB_URL = os.getenv("DB_URL")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DATA_FILES_PATH = os.getenv("DATA_FILES_PATH")


def extract_db_name_from_file_name(file_name):
    return file_name.split("_2024")[0]


def get_existing_tables(cursor):
    cursor.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )
    results = cursor.fetchall()
    tables = [result[0] for result in results]
    return tables


def get_latest_updatetime_for_table(cursor, table):
    cursor.execute(f"SELECT MAX(pickup_datetime) FROM {table}")
    result = cursor.fetchone()[0]
    return result


def get_files_to_process(table_name, start_time):
    end_time = datetime.now()
    # Find the current datetime but in 2024
    end_month = end_time.month
    end_month_str = f"0{end_month}"[
        -2:
    ]  # Add a leading zero in case it was a signle digit month
    end_time = datetime(
        2024,
        end_month,
        end_time.day,
        end_time.hour,
        end_time.minute,
        end_time.second,
        end_time.microsecond,
    )
    if start_time is None:
        start_month = 1
        start_time = datetime(
            2024,
            1,
            1,
        )
    else:
        start_month = start_time.month
    past_months = list(range(start_month, end_month))
    past_month_files = [
        {
            "file_name": f"{table_name}_2024-" + f"0{month}"[-2:] + ".parquet",
            "table_name": table_name,
            "start_time": None,
            "end_time": None,
        }
        for month in past_months
    ]

    all_files_to_process = [
        *past_month_files,
        {
            "file_name": f"{table_name}_2024-{end_month_str}.parquet",
            "table_name": table_name,
            "start_time": start_time,
            "end_time": end_time,
        },
    ]

    print(f"Files to process for {table_name}: ", all_files_to_process)

    return all_files_to_process


@task(log_prints=True)
def discover_files():
    all_files = os.listdir(DATA_FILES_PATH)
    all_potential_tables = list(
        set([extract_db_name_from_file_name(file_name) for file_name in all_files])
    )
    print("All potential tables: ", all_potential_tables)

    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cursor = conn.cursor()

    existing_tables = get_existing_tables(cursor)
    print("Existing tables found: ", existing_tables)

    tables_not_existing = list(set(all_potential_tables) - set(existing_tables))
    print("Tables not existing: ", tables_not_existing)

    tables_start_times = {
        **{table: None for table in tables_not_existing},
        **{
            table: get_latest_updatetime_for_table(cursor, table)
            for table in existing_tables
        },
    }
    print("Table start times: ", tables_start_times)

    cursor.close()
    conn.close()

    files_to_process = []
    for table_name, start_time in tables_start_times.items():
        files_to_process += get_files_to_process(table_name, start_time)
    print("All files identified for processing: ", files_to_process)

    return files_to_process


@flow(log_prints=True, flow_run_name="{file_name}", retries=5)
def ingest_data_from_file(spark, file_name, table_name, start_time, end_time):
    file_path = os.path.join(DATA_FILES_PATH, file_name)
    try:
        # Read the Parquet file
        print(f"Reading Parquet file from {file_path} ...")
        df = spark.read.parquet(file_path)

        pickup_col = [col for col in df.columns if "pickup_datetime" in col.lower()][0]
        dropoff_col = [col for col in df.columns if "dropoff_datetime" in col.lower()][
            0
        ]
        df = df.withColumnsRenamed(
            {pickup_col: "pickup_datetime", dropoff_col: "dropoff_datetime"}
        )

        if start_time is not None and end_time is not None:
            df = df.filter(
                (df["pickup_datetime"] > start_time)
                & (df["pickup_datetime"] < end_time)
            )

        num_rows = df.count()

        if num_rows == 0:
            print(
                f"No data found in {file_path} between {start_time} and {end_time}. Skipping"
            )
        else:
            # Write to PostgreSQL
            print(
                f"Writing {num_rows} DataFrame rows to PostgreSQL table '{table_name}' at {DB_URL} ..."
            )
            df.write.format("jdbc").option("url", DB_URL).option(
                "dbtable", table_name
            ).option("user", DB_USER).option("password", DB_PASSWORD).option(
                "driver", "org.postgresql.Driver"
            ).mode(
                "append"
            ).save()

            print(f"✅ Data successfully written data from {file_path} to PostgreSQL!")

    except Exception as e:
        print(f"❌ Error: {e}")


@flow(log_prints=True, retries=5)
def ingest_data():
    # Identify which files need to be read
    print("Discovering the files to read")
    all_files = discover_files()

    # Initialize Spark session
    spark = (
        SparkSession.builder.appName("ParquetToPostgres")
        .config("spark.jars", "/opt/spark/jars/postgresql-42.5.0.jar")
        .getOrCreate()
    )

    # Ingest data from each file
    for file_data in all_files:
        ingest_data_from_file(spark, **file_data)

    # Stop Spark session
    spark.stop()
    print("Spark session stopped.")


@flow(log_prints=True, flow_run_name="{mat_view_name}", retries=5)
def create_or_update_mat_view(
    mat_view_name, mat_view_query, idx_col_name, conn, existing_mat_views
):
    cursor = conn.cursor()
    if mat_view_name in existing_mat_views:
        print(f"Materialized view {mat_view_name} already exists. Refreshing it")
        cursor.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mat_view_name};")
        conn.commit()
        print(f"Successfully refreshed the materialized view {mat_view_name}")
    else:
        print(f"Materialized view {mat_view_name} doesn't exist. Creating it")
        cursor.execute(mat_view_query)
        conn.commit()
        print(
            f"Done creating {mat_view_name} materialized view. Going to create unique index"
        )
        cursor.execute(
            f"CREATE UNIQUE INDEX {mat_view_name}_idx ON {mat_view_name} ({idx_col_name});"
        )
        conn.commit()
    cursor.close()


@flow(log_prints=True, retries=5)
def create_or_update_all_materialized_views():
    fhvhv_hourly_tripdata = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS fhvhv_hourly_tripdata AS
        SELECT
            DATE_TRUNC('hour', pickup_datetime) AS pickup_hour,
            COUNT(*) AS num_trips,
            AVG(EXTRACT(EPOCH FROM (on_scene_datetime::timestamp - request_datetime::timestamp)) / 60) AS avg_request_to_on_scene_time_min,
            AVG(trip_time/60) AS avg_trip_time_min,
            AVG(trip_miles) AS avg_trip_miles,
            SUM(base_passenger_fare) AS total_base_fare_amount,
            SUM(tolls) AS total_tolls,
            SUM(bcf) AS total_black_car_fund,
            SUM(sales_tax) AS total_tax,
            SUM(congestion_surcharge) AS total_congestion_surcharge,
            SUM(airport_fee) AS total_airport_fees,
            SUM(tips) AS total_tips,
            SUM(driver_pay) AS total_driver_pay,
            SUM(base_passenger_fare) + SUM(tolls) + SUM(bcf) + SUM(sales_tax) + SUM(congestion_surcharge) + SUM(airport_fee) + SUM(tips) AS total_amount_payed
        FROM fhvhv_tripdata
        GROUP BY pickup_hour
    """

    fhv_hourly_tripdata = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS fhv_hourly_tripdata AS
        SELECT
            DATE_TRUNC('hour', pickup_datetime) AS pickup_hour,
            COUNT(*) AS num_trips,
            AVG(EXTRACT(EPOCH FROM (dropoff_datetime::timestamp - pickup_datetime::timestamp)) / 60) AS avg_trip_time_min
        FROM fhv_tripdata
        GROUP BY pickup_hour
    """

    yellow_hourly_tripdata = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS yellow_hourly_tripdata AS
            SELECT
            DATE_TRUNC('hour', pickup_datetime) AS pickup_hour,
            COUNT(*) AS num_trips,
            AVG(EXTRACT(EPOCH FROM (dropoff_datetime::timestamp - pickup_datetime::timestamp)) / 60) AS avg_trip_time_min,
            AVG(trip_distance) AS avg_trip_miles,
            SUM(fare_amount) AS total_base_fare_amount,
            SUM(extra) AS total_extra,
            SUM(mta_tax) AS total_tax,
            SUM(tip_amount) AS total_tips,
            SUM(tolls_amount) AS total_tolls,
            SUM(improvement_surcharge) AS total_improvement_surcharge,
            SUM(congestion_surcharge) AS total_congestion_surcharge,
            SUM("Airport_fee") AS total_airport_fees,
            SUM(fare_amount) + SUM(extra) + SUM(mta_tax) + SUM(tip_amount) + SUM(tolls_amount) + SUM(improvement_surcharge) + SUM(congestion_surcharge) + SUM("Airport_fee") AS total_amount_payed
        FROM yellow_tripdata
        GROUP BY pickup_hour
    """

    green_hourly_tripdata = """
        CREATE MATERIALIZED VIEW IF NOT EXISTS green_hourly_tripdata AS
        SELECT
            DATE_TRUNC('hour', pickup_datetime) AS pickup_hour,
            COUNT(*) AS num_trips,
            AVG(EXTRACT(EPOCH FROM (dropoff_datetime::timestamp - pickup_datetime::timestamp)) / 60) AS avg_trip_time_min,
            AVG(trip_distance) AS avg_trip_miles,
            SUM(fare_amount) AS total_base_fare_amount,
            SUM(extra) AS total_extra,
            SUM(mta_tax) AS total_tax,
            SUM(tip_amount) AS total_tips,
            SUM(tolls_amount) AS total_tolls,
            SUM(improvement_surcharge) AS total_improvement_surcharge,
            SUM(congestion_surcharge) AS total_congestion_surcharge,
            SUM(fare_amount) + SUM(extra) + SUM(mta_tax) + SUM(tip_amount) + SUM(tolls_amount) + SUM(improvement_surcharge) + SUM(congestion_surcharge) AS total_amount_payed
        FROM green_tripdata
        GROUP BY pickup_hour
    """

    mat_views_queries = {
        "fhvhv_hourly_tripdata": fhvhv_hourly_tripdata,
        "fhv_hourly_tripdata": fhv_hourly_tripdata,
        "yellow_hourly_tripdata": yellow_hourly_tripdata,
        "green_hourly_tripdata": green_hourly_tripdata,
    }

    # Creating connection to the DB
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cursor = conn.cursor()
    cursor.execute("SELECT matviewname FROM pg_matviews")
    results = cursor.fetchall()
    existing_mat_views = [result[0] for result in results]
    for name, query in mat_views_queries.items():
        print(f"Working on {name} materialized view")
        create_or_update_mat_view(
            mat_view_name=name,
            mat_view_query=query,
            idx_col_name="pickup_hour",
            conn=conn,
            existing_mat_views=existing_mat_views,
        )
    # Closing connection to the DB
    cursor.close()
    conn.close()


if __name__ == "__main__":

    def serve1():
        ingest_data.serve(
            name="data-ingestion-deployment",
            schedules=[IntervalSchedule(interval=timedelta(minutes=60))],
        )

    def serve2():
        create_or_update_all_materialized_views.serve(
            name="data-aggregation-deployment",
            schedules=[IntervalSchedule(interval=timedelta(minutes=60))],
        )

    p1 = multiprocessing.Process(target=serve1)
    p2 = multiprocessing.Process(target=serve2)

    p1.start()
    p2.start()

    p1.join()
    p2.join()
