import os
from datetime import date, datetime

import bcrypt
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Dash, Input, Output, State, callback, dcc, html
from flask import Flask, redirect, request
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy import create_engine
from utils import *

DB_URL = os.getenv("DB_URL")
DASHBOARD_USER = os.getenv("DASHBOARD_USER")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD")

AGGREGATION_TIME_MAP = {
    "By hour of day": "hour_of_day",
    "By day of week": "day_of_week",
    "By day of month": "day_of_month",
    "By month": "month",
}

SUMMED_METRICS_MAP = {
    "Total number of trips": "num_trips",
    "Total amounts payed": "total_amount_payed",
}

AVG_METRICS_MAP = {
    "Average trip duration, min": "avg_trip_time_min",
    "Average trim distance, miles": "avg_trip_miles",
    "Average taxi request - on scene time, min": "avg_request_to_on_scene_time_min",
}

PRICE_CONTRIBUTORS = {
    "fhvhv": [
        "total_base_fare_amount",
        "total_tolls",
        "total_black_car_fund",
        "total_tax",
        "total_congestion_surcharge",
        "total_airport_fees",
        "total_tips",
        "total_driver_pay",
    ],
    "yellow": [
        "total_base_fare_amount",
        "total_extra",
        "total_tax",
        "total_tips",
        "total_tolls",
        "total_improvement_surcharge",
        "total_congestion_surcharge",
        "total_airport_fees",
    ],
    "green": [
        "total_base_fare_amount",
        "total_extra",
        "total_tax",
        "total_tips",
        "total_tolls",
        "total_improvement_surcharge",
        "total_congestion_surcharge",
    ],
}

# ----------- Flask App Setup -----------
server = Flask(__name__)
server.secret_key = os.getenv("SERVER_SECRET_KEY")

# ----------- Flask-Login Setup -----------
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = "/login"


# ----------- User Class -----------
class User(UserMixin):
    def __init__(self, id):
        self.id = id


# ----------- In-Memory User Store with bcrypt-hashed passwords -----------
USERS = {
    DASHBOARD_USER: bcrypt.hashpw(DASHBOARD_PASSWORD.encode(), bcrypt.gensalt()),
}


@login_manager.user_loader
def load_user(user_id):
    return User(user_id)


now = datetime.now()
now_2024_date = date(2024, now.month, now.day)

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.SUPERHERO],
    server=server,
    url_base_pathname="/dashboard/",
)

app.title = "NYC Taxi Trip Data"

CENTER_STYLE = {"text-alignhjh": "center"}


@server.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password").encode("utf-8")

        if username in USERS:
            stored_hash = USERS[username]
            if bcrypt.checkpw(password, stored_hash):
                login_user(User(username))
                return redirect("/dashboard/")
        return """
            <div style="text-align:center; margin-top: 50px;">
                <p style="color:red;">Invalid credentials. Try again.</p>
                <a href="/login">Back to login</a>
            </div>
        """

    return LOGIN_FORM


@server.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")


@app.server.before_request
def restrict_dash():
    if request.path.startswith("/dashboard") and not current_user.is_authenticated:
        return redirect("/login")


app.layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card([dbc.CardBody(html.H2("NYC Taxi Trip Data"))]), width=11
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardBody(
                                html.A(
                                    "Logout",
                                    href="/logout",
                                    className="btn btn-outline-danger",
                                ),
                                className="d-flex align-items-center justify-content-center h-100",
                            )
                        ]
                    ),
                    width=1,
                ),
            ],
            className="text-center sticky-top",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Choose a date range"),
                            dbc.CardBody(
                                dcc.DatePickerRange(
                                    id="date-range",
                                    min_date_allowed=date(2024, 1, 1),
                                    max_date_allowed=date(2024, 12, 31),
                                    start_date=date(2024, 2, 1),
                                    end_date=now_2024_date,
                                ),
                            ),
                        ],
                        className="h-100",
                    ),
                    width=3,
                )
            ],
            justify="center",
            className="text-center mt-2",
        ),
        dbc.Row(html.H4("Number of trips"), className="text-center mt-4"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("FHVHV"),
                                dbc.CardBody(0, id="num-trips-fhvhv"),
                            ],
                            className="mb-2",
                        )
                    ],
                    width=3,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("FHV"),
                                dbc.CardBody(0, id="num-trips-fhv"),
                            ],
                            className="mb-2",
                        )
                    ],
                    width=3,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Yellow"),
                                dbc.CardBody(0, id="num-trips-yellow"),
                            ],
                            className="mb-2",
                        )
                    ],
                    width=3,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Green"),
                                dbc.CardBody(0, id="num-trips-green"),
                            ],
                            className="mb-2",
                        )
                    ],
                    width=3,
                ),
            ],
            className="mb-2 text-center",
        ),
        dbc.Row(html.H4("Total amounts payed"), className="text-center mt-4"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("FHVHV"),
                                dbc.CardBody(0, id="total-payment-fhvhv"),
                            ],
                            className="mb-2",
                        )
                    ],
                    width=3,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("FHV"),
                                dbc.CardBody(
                                    "Payment data not available", id="total-payment-fhv"
                                ),
                            ],
                            className="mb-2",
                        )
                    ],
                    width=3,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Yellow"),
                                dbc.CardBody(0, id="total-payment-yellow"),
                            ],
                            className="mb-2",
                        )
                    ],
                    width=3,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Green"),
                                dbc.CardBody(0, id="total-payment-green"),
                            ],
                            className="mb-2",
                        )
                    ],
                    width=3,
                ),
            ],
            className="mb-2 text-center",
        ),
        dbc.Row(html.H3("1. Summed metrics over time"), className="text-center mt-4"),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Choose a metric to visualize"),
                            dbc.CardBody(
                                dcc.Dropdown(
                                    options=list(SUMMED_METRICS_MAP.keys()),
                                    value=list(SUMMED_METRICS_MAP.keys())[0],
                                    placeholder="Choose metric",
                                    style={"color": "black"},
                                    id="summed-metric",
                                )
                            ),
                        ],
                        className="h-100",
                    ),
                    width=3,
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Choose time range to group by"),
                            dbc.CardBody(
                                dcc.Dropdown(
                                    options=list(AGGREGATION_TIME_MAP.keys()),
                                    value=list(AGGREGATION_TIME_MAP.keys())[0],
                                    placeholder="Aggregation range",
                                    style={"color": "black"},
                                    id="summed-metric-time-unit",
                                )
                            ),
                        ],
                        className="h-100",
                    ),
                    width=3,
                ),
            ],
            justify="center",
            className="text-center",
        ),
        dbc.Row(html.H4("", id="summed-metric-title"), className="text-center mt-4"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("FHVHV"),
                                dbc.CardBody([], id="summed-metric-fhvhv"),
                            ]
                        ),
                    ],
                    width=6,
                    className="mt-2",
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("FHV"),
                                dbc.CardBody([], id="summed-metric-fhv"),
                            ]
                        ),
                    ],
                    width=6,
                    className="mt-2",
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Yellow"),
                                dbc.CardBody([], id="summed-metric-yellow"),
                            ]
                        ),
                    ],
                    width=6,
                    className="mt-2",
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Green"),
                                dbc.CardBody([], id="summed-metric-green"),
                            ]
                        ),
                    ],
                    width=6,
                    className="mt-2",
                ),
            ],
            className="text-center",
        ),
        dbc.Row(
            html.H3("2. Contributions to total prices payed"),
            className="text-center mt-4",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("FHVHV"),
                                dbc.CardBody(
                                    dcc.Graph(
                                        figure={},
                                        config={"displayModeBar": False},
                                        id="price-conts-fhvhv",
                                    )
                                ),
                            ]
                        ),
                    ],
                    width=6,
                    className="mt-2",
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [dbc.CardHeader("FHV"), dbc.CardBody("DATA NOT AVAILABLE")]
                        ),
                    ],
                    width=6,
                    className="mt-2",
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Yellow"),
                                dbc.CardBody(
                                    dcc.Graph(
                                        figure={},
                                        config={"displayModeBar": False},
                                        id="price-conts-yellow",
                                    )
                                ),
                            ]
                        ),
                    ],
                    width=6,
                    className="mt-2",
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Green"),
                                dbc.CardBody(
                                    dcc.Graph(
                                        figure={},
                                        config={"displayModeBar": False},
                                        id="price-conts-green",
                                    )
                                ),
                            ]
                        ),
                    ],
                    width=6,
                    className="mt-2",
                ),
            ],
            className="text-center",
        ),
        dbc.Row(html.H3("3. Other metric distribution"), className="text-center mt-4"),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Choose a metric to visualize"),
                            dbc.CardBody(
                                dcc.Dropdown(
                                    options=list(AVG_METRICS_MAP.keys()),
                                    value=list(AVG_METRICS_MAP.keys())[0],
                                    placeholder="Choose metric",
                                    style={"color": "black"},
                                    id="avg-metric",
                                )
                            ),
                        ],
                        className="h-100",
                    ),
                    width=3,
                ),
            ],
            justify="center",
            className="text-center",
        ),
        dbc.Row(html.H4("", id="avg-metric-title"), className="text-center mt-4"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("FHVHV"),
                                dbc.CardBody([], id="avg-metric-fhvhv"),
                            ]
                        ),
                    ],
                    width=6,
                    className="mt-2",
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("FHV"),
                                dbc.CardBody([], id="avg-metric-fhv"),
                            ]
                        ),
                    ],
                    width=6,
                    className="mt-2",
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Yellow"),
                                dbc.CardBody([], id="avg-metric-yellow"),
                            ]
                        ),
                    ],
                    width=6,
                    className="mt-2",
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Green"),
                                dbc.CardBody([], id="avg-metric-green"),
                            ]
                        ),
                    ],
                    width=6,
                    className="mt-2",
                ),
            ],
            className="text-center",
        ),
        dbc.Row(html.H3("4. Data download"), className="text-center mt-4"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("FHVHV"),
                                dbc.CardBody(
                                    [
                                        html.Button(
                                            "Download",
                                            id="hfvhv-download-button",
                                            style={"width": "100%"},
                                        ),
                                        dcc.Download(id="fhvhv-download-csv"),
                                    ]
                                ),
                            ]
                        ),
                    ],
                    width=3,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("FHV"),
                                dbc.CardBody(
                                    [
                                        html.Button(
                                            "Download",
                                            id="hfv-download-button",
                                            style={"width": "100%"},
                                        ),
                                        dcc.Download(id="fhv-download-csv"),
                                    ]
                                ),
                            ]
                        ),
                    ],
                    width=3,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Yellow"),
                                dbc.CardBody(
                                    [
                                        html.Button(
                                            "Download",
                                            id="yellow-download-button",
                                            style={"width": "100%"},
                                        ),
                                        dcc.Download(id="yellow-download-csv"),
                                    ]
                                ),
                            ]
                        ),
                    ],
                    width=3,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader("Green"),
                                dbc.CardBody(
                                    [
                                        html.Button(
                                            "Download",
                                            id="green-download-button",
                                            style={"width": "100%"},
                                        ),
                                        dcc.Download(id="green-download-csv"),
                                    ]
                                ),
                            ]
                        ),
                    ],
                    width=3,
                ),
            ],
            className="text-center",
        ),
        # These are not for display, but rather for managing data refreshing
        dcc.Interval(
            id="data-refresh-component",
            interval=720 * 1000,  # 1 hour in milliseconds
            n_intervals=0,
        ),
        dcc.Store(id="global-data-store"),
    ],
    fluid=True,
)


@callback(
    Output("num-trips-fhvhv", "children"),
    Output("num-trips-fhv", "children"),
    Output("num-trips-yellow", "children"),
    Output("num-trips-green", "children"),
    Output("total-payment-fhvhv", "children"),
    Output("total-payment-yellow", "children"),
    Output("total-payment-green", "children"),
    Input("date-range", "start_date"),
    Input("date-range", "end_date"),
    Input("global-data-store", "data"),
)
def update_stats(start_date, end_date, data):
    fhvhv_df = pd.DataFrame(data["fhvhv_data"])
    fhv_df = pd.DataFrame(data["fhv_data"])
    yellow_df = pd.DataFrame(data["yellow_data"])
    green_df = pd.DataFrame(data["green_data"])
    yellow_df_2 = yellow_df.query("@start_date<=pickup_hour<=@end_date")
    green_df_2 = green_df.query("@start_date<=pickup_hour<=@end_date")
    fhvhv_df_2 = fhvhv_df.query("@start_date<=pickup_hour<=@end_date")
    hfv_df_2 = fhv_df.query("@start_date<=pickup_hour<=@end_date")
    return (
        fhvhv_df_2["num_trips"].sum(),
        hfv_df_2["num_trips"].sum(),
        yellow_df_2["num_trips"].sum(),
        green_df_2["num_trips"].sum(),
        round(fhvhv_df_2["total_amount_payed"].sum(), 2),
        round(yellow_df_2["total_amount_payed"].sum(), 2),
        round(green_df_2["total_amount_payed"].sum(), 2),
    )


@callback(
    Output("summed-metric-title", "children"),
    Output("summed-metric-fhvhv", "children"),
    Output("summed-metric-fhv", "children"),
    Output("summed-metric-yellow", "children"),
    Output("summed-metric-green", "children"),
    Input("date-range", "start_date"),
    Input("date-range", "end_date"),
    Input("summed-metric", "value"),
    Input("summed-metric-time-unit", "value"),
    Input("global-data-store", "data"),
)
def update_summed_metrics(start_date, end_date, summed_metric, time_range, data):
    fhvhv_df = pd.DataFrame(data["fhvhv_data"])
    fhv_df = pd.DataFrame(data["fhv_data"])
    yellow_df = pd.DataFrame(data["yellow_data"])
    green_df = pd.DataFrame(data["green_data"])
    time_col = AGGREGATION_TIME_MAP[time_range]
    y_col = SUMMED_METRICS_MAP[summed_metric]
    return (
        f"{summed_metric} {time_range}",
        plot_trend(
            df=fhvhv_df,
            time_col=time_col,
            y_col=y_col,
            start_date=start_date,
            end_date=end_date,
        ),
        plot_trend(
            df=fhv_df,
            time_col=time_col,
            y_col=y_col,
            start_date=start_date,
            end_date=end_date,
        ),
        plot_trend(
            df=yellow_df,
            time_col=time_col,
            y_col=y_col,
            start_date=start_date,
            end_date=end_date,
        ),
        plot_trend(
            df=green_df,
            time_col=time_col,
            y_col=y_col,
            start_date=start_date,
            end_date=end_date,
        ),
    )


@callback(
    Output("avg-metric-title", "children"),
    Output("avg-metric-fhvhv", "children"),
    Output("avg-metric-fhv", "children"),
    Output("avg-metric-yellow", "children"),
    Output("avg-metric-green", "children"),
    Input("date-range", "start_date"),
    Input("date-range", "end_date"),
    Input("avg-metric", "value"),
    Input("global-data-store", "data"),
)
def update_avg_metrics(start_date, end_date, avg_metric, data):
    fhvhv_df = pd.DataFrame(data["fhvhv_data"])
    fhv_df = pd.DataFrame(data["fhv_data"])
    yellow_df = pd.DataFrame(data["yellow_data"])
    green_df = pd.DataFrame(data["green_data"])
    x_col = AVG_METRICS_MAP[avg_metric]
    return (
        f"Distribution of the {avg_metric}",
        plot_histogram(df=fhvhv_df, x=x_col, start_date=start_date, end_date=end_date),
        plot_histogram(df=fhv_df, x=x_col, start_date=start_date, end_date=end_date),
        plot_histogram(df=yellow_df, x=x_col, start_date=start_date, end_date=end_date),
        plot_histogram(df=green_df, x=x_col, start_date=start_date, end_date=end_date),
    )


@callback(
    Output("price-conts-fhvhv", "figure"),
    Output("price-conts-yellow", "figure"),
    Output("price-conts-green", "figure"),
    Input("date-range", "start_date"),
    Input("date-range", "end_date"),
    Input("global-data-store", "data"),
)
def update_price_contributors(start_date, end_date, data):
    fhvhv_df = pd.DataFrame(data["fhvhv_data"])
    yellow_df = pd.DataFrame(data["yellow_data"])
    green_df = pd.DataFrame(data["green_data"])
    return (
        plot_price_contributors(
            df=fhvhv_df,
            start_date=start_date,
            end_date=end_date,
            cols=PRICE_CONTRIBUTORS["fhvhv"],
        ),
        plot_price_contributors(
            df=yellow_df,
            start_date=start_date,
            end_date=end_date,
            cols=PRICE_CONTRIBUTORS["yellow"],
        ),
        plot_price_contributors(
            df=green_df,
            start_date=start_date,
            end_date=end_date,
            cols=PRICE_CONTRIBUTORS["green"],
        ),
    )


@callback(
    Output("fhvhv-download-csv", "data"),
    Input("hfvhv-download-button", "n_clicks"),
    State("date-range", "start_date"),
    State("date-range", "end_date"),
    State("global-data-store", "data"),
    prevent_initial_call=True,
)
def download_fhvhv_data(n_clicks, start_date, end_date, data):
    fhvhv_df = pd.DataFrame(data["fhvhv_data"])
    return download_data(fhvhv_df, "fhvhv", start_date, end_date)


@callback(
    Output("yellow-download-csv", "data"),
    Input("yellow-download-button", "n_clicks"),
    State("date-range", "start_date"),
    State("date-range", "end_date"),
    State("global-data-store", "data"),
    prevent_initial_call=True,
)
def download_yellow_data(n_clicks, start_date, end_date, data):
    yellow_df = pd.DataFrame(data["yellow_data"])
    return download_data(yellow_df, "yellow", start_date, end_date)


@callback(
    Output("green-download-csv", "data"),
    Input("green-download-button", "n_clicks"),
    State("date-range", "start_date"),
    State("date-range", "end_date"),
    State("global-data-store", "data"),
    prevent_initial_call=True,
)
def download_green_data(n_clicks, start_date, end_date, data):
    green_df = pd.DataFrame(data["green_data"])
    return download_data(green_df, "green", start_date, end_date)


@callback(
    Output("fhv-download-csv", "data"),
    Input("hfv-download-button", "n_clicks"),
    State("date-range", "start_date"),
    State("date-range", "end_date"),
    State("global-data-store", "data"),
    prevent_initial_call=True,
)
def download_fhv_data(n_clicks, start_date, end_date, data):
    fhv_df = pd.DataFrame(data["fhv_data"])
    return download_data(fhv_df, "fhv", start_date, end_date)


@callback(
    Output("global-data-store", "data"), Input("data-refresh-component", "n_intervals")
)
def update_global_data(n_intervals):
    engine = create_engine(DB_URL)
    fhvhv_data = fetch_data(table="fhvhv_hourly_tripdata", engine=engine)
    fhv_data = fetch_data(table="fhv_hourly_tripdata", engine=engine)
    yellow_data = fetch_data(table="yellow_hourly_tripdata", engine=engine)
    green_data = fetch_data(table="green_hourly_tripdata", engine=engine)
    engine.dispose()
    return dict(
        fhvhv_data=fhvhv_data,
        fhv_data=fhv_data,
        yellow_data=yellow_data,
        green_data=green_data,
    )


if __name__ == "__main__":
    print("Starting app")
    app.run(host="0.0.0.0", port=8053)
