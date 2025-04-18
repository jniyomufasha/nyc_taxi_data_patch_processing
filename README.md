# NYC Taxi Data Batch Processing

This is a batch processing pipeline that uses [NYC taxi data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).
It comprises a `data ingestion` service which ingests raw data from parquet trip data files using `Apache Spark`.
The data aggregation service aggregates data into materialized view, which powers a front end dashboard, powered by `Dash Plotly`.

These 2 processs run every hours and the job scheduling is handled through `Prefect`, a workflow orchestration platform that simplifies the process of building,
managing, and monitoring data pipelines and machine learning workflows, allowing developers to write and run data pipelines in pure
Python without the need for complex DSLs or configuration files.

All these services and other supporting services such as databases are orchestrated using `docker compose`.

In addition, we set up monitoring services, using `cAdvisor` for collecting container performance metrics, storing them using `prometheus` and visualizing them using `grafana`.

## Running Locally

1. Clone this repo
2. Change to nyc_taxi_data_patch_processing
```
cd nyc_taxi_data_patch_processing
```
3. Download the data ([link](https://drive.google.com/file/d/1FThjG8qPvVFkcQ9yzKMrios-UEg8FqKx/view?usp=sharing)) and extract data folder into `nyc_taxi_data_patch_processing/`
4. As per good practice, credectials should not be pushed on github. For reproducing locally,
download [this .env file](https://drive.google.com/file/d/17csV42Z3vldNCh6ppxwA_iBVCXeGK7RV/view?usp=sharing) and also put it in `nyc_taxi_data_patch_processing/`

  The layout should be (ommiting the rest of the files in the root folder)
  ```
  nyc_taxi_data_patch_processing/
                  |
                  |--data/
                  |
                  |--src/
                  |
                  |--.env
```
5. Update the permissions (grant execute access) to the files for starting and stopping the containers
```
chmod +x start.sh
chmod +x stop.sh
```
6. Start the containers running
```
./start.sh
```
This will start the containers in the detached mode.

When the containers run: they will expose 3 ports which will be accessible to the local host:
`http://localhost:4200/` for the prefect dashboard for prefect flow management, `http://localhost:8053/dashboard/` for the frontend dashboard,
and `http://localhost:3025/` for grafana, visualizing and monitoring the performance of the docker containers.

* **Prefect Dashboard**

  <img width="1709" alt="image" src="https://github.com/user-attachments/assets/b7b59454-2c66-4cbb-9ea5-bad6d2212337" />
This helps monitor the status of the prefect flows, their run states and logs.

When prefect starts, it will schedule the first run in one hour. To trigger it immediately for visualizing the results, go to `Deployments` and you will see 2 deployments:
`data-ingestion-deployment` and `data-aggregation-deployment`. You can trigger a quick run for each of them, first `data-ingestion-deployment` then `data-aggregation-deployment`.
The order matters a lot, because the aggregation deployment will be aggregating on the data ingested by the ingestion deployment. Therefore, it's necessary to not run the aggregation deployment
until the ingestion deployment is done running (green vertical bars).
<img width="1709" alt="image" src="https://github.com/user-attachments/assets/fa052e34-628e-4193-8a18-da9f3425bdcf" />

* **Dash Frontend Dashboard**

<img width="1709" alt="image" src="https://github.com/user-attachments/assets/c5da1179-be75-4c0f-83a6-44f88838a01f" />

This visualizes different metrics for the taxi operations in NYC, with input widgets for dynamically changing the visualizations.
It is worth noting that it is password protected. The username is `user` and the password is `brsuhdbgbdrthbgvjhkdbkjhfgbtdruhfvukgh`

* **Grafana**
  
  It will be used to visualize the performance metrics of the container.
  When visiting grafana for the first time, you will be presented with a login form. The user will be `admin` and password will be `admin`.
  Then you will be asked to input a new password. Put a password of your choice.

  Once in, you can view the dashboard by clicking `Dashboards` on the left side menu, then `Docker Monitoring Dashboard` and you will see the dasboard below.
  It displays different metrics, including CPU usage, memory usage, network, read and write speeds, etc.

  <img width="1709" alt="image" src="https://github.com/user-attachments/assets/3b59b520-7c35-46d0-ada8-43b8b0e1f8ef" />


7. To stop the containers, run 
```
./stop.sh
```
