import pandas as pd
import plotly.express as px
from dash import dcc


def generate_query(table):
    return f"""
    SELECT
        DATE_PART('hour', pickup_hour) AS hour_of_day,
        DATE_PART('dow', pickup_hour) AS day_of_week,
        DATE_PART('day', pickup_hour) AS day_of_month,
        DATE_PART('month', pickup_hour) AS month,
        *
    FROM {table}
    ORDER BY pickup_hour
    """


def fetch_data(table, engine):
    df = pd.read_sql(generate_query(table), engine)
    return df.to_dict("records")


def plot_trend(df, time_col, y_col, start_date, end_date, agg="sum"):
    if not time_col in df or not y_col in df:
        return "DATA NOT AVAILABLE"
    grouped = (
        df.query("@start_date<=pickup_hour<=@end_date")
        .groupby(time_col)
        .agg({y_col: agg})
        .reset_index()
    )
    fig = px.bar(grouped, x=time_col, y=y_col, text=y_col)
    fig.update_traces(textposition="outside")
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def plot_price_contributors(df, cols, start_date, end_date):
    summed_df = (
        df.query("@start_date<=pickup_hour<=@end_date")[cols]
        .sum(axis=0)
        .to_frame()
        .reset_index()
        .rename(columns={"index": "expense", 0: "amount"})
    )
    summed_df["expense"] = summed_df["expense"].apply(lambda x: x.replace("total_", ""))
    fig = px.bar(summed_df, x="expense", y="amount", text="amount")
    return fig


def plot_histogram(df, x, start_date, end_date):
    if x not in df:
        return "DATA NOT AVAILABLE"
    df_time_filtered = df.query("@start_date<=pickup_hour<=@end_date")
    variable_95_percentile = df_time_filtered[x].quantile(0.99)
    df_percentile_filtered = df_time_filtered[
        df_time_filtered[x] <= variable_95_percentile
    ]
    fig = px.histogram(df_percentile_filtered[x])
    fig.update_layout(bargap=0.05, showlegend=False)
    fig.update_traces(texttemplate="%{y}", textposition="outside")
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def download_data(df, df_name, start_date, end_date):
    return dcc.send_data_frame(
        df.query("@start_date<=pickup_hour<=@end_date").to_csv,
        filename=f"{df_name}_from_{start_date}_to_{end_date}.csv",
    )


LOGIN_FORM = """
    <html>
    <head>
        <title>Login</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f7f7f7;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
            }
            .login-container {
                background-color: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                width: 300px;
            }
            .login-container h2 {
                text-align: center;
                margin-bottom: 20px;
            }
            .login-container input {
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                border-radius: 5px;
                border: 1px solid #ccc;
                font-size: 14px;
            }
            .login-container input[type="submit"] {
                background-color: #007bff;
                color: white;
                border: none;
                cursor: pointer;
                transition: background-color 0.2s ease;
            }
            .login-container input[type="submit"]:hover {
                background-color: #0056b3;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h2>Login</h2>
            <form method="POST">
                <input type="text" name="username" placeholder="Username" required/><br/>
                <input type="password" name="password" placeholder="Password" required/><br/>
                <input type="submit" value="Login"/>
            </form>
        </div>
    </body>
    </html>
    """
