"""Dash dashboard for the Learning Analytics Intelligence Platform."""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html


DASHBOARD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DASHBOARD_DIR.parent
WAREHOUSE_PATH = PROJECT_ROOT / "data" / "warehouse" / "laip.duckdb"

MART_TABLES = {
    "student_module": "dim_student_module",
    "course_engagement_daily": "fct_course_engagement_daily",
    "assessment_performance": "fct_assessment_performance",
}

EXPECTED_COLUMNS = {
    "student_module": [
        "code_module",
        "code_presentation",
        "id_student",
        "final_result",
        "is_withdrawn",
    ],
    "course_engagement_daily": [
        "code_module",
        "code_presentation",
        "activity_date",
        "active_students",
        "total_clicks",
    ],
    "assessment_performance": [
        "code_module",
        "code_presentation",
        "assessment_type",
        "submitted_assessments",
        "average_score",
    ],
}


def load_mart_table(table_key: str) -> pd.DataFrame:
    """Load one approved mart table from the local DuckDB warehouse."""
    table_name = MART_TABLES[table_key]
    if not WAREHOUSE_PATH.exists():
        return pd.DataFrame(columns=EXPECTED_COLUMNS[table_key])

    query = f"select * from {table_name}"
    try:
        with duckdb.connect(str(WAREHOUSE_PATH), read_only=True) as connection:
            return connection.execute(query).fetchdf()
    except duckdb.Error:
        return pd.DataFrame(columns=EXPECTED_COLUMNS[table_key])


def load_dashboard_data() -> dict[str, pd.DataFrame]:
    """Load all dashboard data from approved dbt mart tables."""
    return {table_key: load_mart_table(table_key) for table_key in MART_TABLES}


def filter_by_scope(
    data_frame: pd.DataFrame,
    code_module: str | None,
    code_presentation: str | None,
) -> pd.DataFrame:
    """Filter a mart data frame by selected module and presentation."""
    filtered = data_frame
    if code_module and "code_module" in filtered.columns:
        filtered = filtered[filtered["code_module"] == code_module]
    if code_presentation and "code_presentation" in filtered.columns:
        filtered = filtered[filtered["code_presentation"] == code_presentation]
    return filtered


def dropdown_options(values: pd.Series) -> list[dict[str, str]]:
    """Build Dash dropdown options from a pandas series."""
    clean_values = sorted(value for value in values.dropna().unique())
    return [{"label": str(value), "value": value} for value in clean_values]


def empty_figure(message: str):
    """Build a consistent empty-state chart."""
    figure = px.scatter(title=message)
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    figure.update_layout(
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
            }
        ],
        plot_bgcolor="white",
    )
    return figure


def format_number(value: float | int) -> str:
    """Format dashboard numbers for KPI cards."""
    return f"{value:,.0f}"


def format_percent(value: float) -> str:
    """Format dashboard percentages for KPI cards."""
    return f"{value:.1f}%"


def weighted_average(
    data_frame: pd.DataFrame,
    value_column: str,
    weight_column: str,
) -> float | None:
    """Calculate a weighted average when value and weight columns are available."""
    if data_frame.empty:
        return None

    valid_rows = data_frame[[value_column, weight_column]].dropna()
    if valid_rows.empty:
        return None

    weight_total = valid_rows[weight_column].sum()
    if weight_total == 0:
        return None

    return float(
        (valid_rows[value_column] * valid_rows[weight_column]).sum() / weight_total
    )


def build_kpi_cards(
    students: pd.DataFrame,
    engagement: pd.DataFrame,
    assessments: pd.DataFrame,
) -> list[html.Div]:
    """Build KPI cards from filtered mart data."""
    total_enrollments = len(students)
    withdrawal_rate = (
        float(students["is_withdrawn"].mean() * 100)
        if total_enrollments and "is_withdrawn" in students
        else 0.0
    )
    total_clicks = (
        float(engagement["total_clicks"].sum())
        if "total_clicks" in engagement.columns
        else 0.0
    )
    average_score = weighted_average(
        assessments,
        value_column="average_score",
        weight_column="submitted_assessments",
    )

    kpis = [
        ("Total Enrollments", format_number(total_enrollments)),
        ("Withdrawal Rate", format_percent(withdrawal_rate)),
        ("Total Clicks", format_number(total_clicks)),
        (
            "Average Assessment Score",
            f"{average_score:.1f}" if average_score is not None else "N/A",
        ),
    ]
    return [kpi_card(label, value) for label, value in kpis]


def kpi_card(label: str, value: str) -> html.Div:
    """Render one KPI card."""
    return html.Div(
        [
            html.Div(label, style={"fontSize": "0.85rem", "color": "#52606d"}),
            html.Div(
                value,
                style={
                    "fontSize": "1.7rem",
                    "fontWeight": "700",
                    "marginTop": "0.35rem",
                },
            ),
        ],
        style={
            "border": "1px solid #d9e2ec",
            "borderRadius": "8px",
            "padding": "1rem",
            "backgroundColor": "white",
        },
    )


def build_clicks_figure(engagement: pd.DataFrame):
    """Build total clicks trend chart."""
    if engagement.empty:
        return empty_figure("No engagement data available")

    chart_data = engagement.sort_values("activity_date")
    return px.line(
        chart_data,
        x="activity_date",
        y="total_clicks",
        title="Total Clicks Over Time",
        labels={"activity_date": "Activity Date", "total_clicks": "Total Clicks"},
    )


def build_active_students_figure(engagement: pd.DataFrame):
    """Build active students trend chart."""
    if engagement.empty:
        return empty_figure("No active student data available")

    chart_data = engagement.sort_values("activity_date")
    return px.line(
        chart_data,
        x="activity_date",
        y="active_students",
        title="Active Students Over Time",
        labels={
            "activity_date": "Activity Date",
            "active_students": "Active Students",
        },
    )


def build_final_result_figure(students: pd.DataFrame):
    """Build final result distribution chart."""
    if students.empty:
        return empty_figure("No student outcome data available")

    chart_data = (
        students.groupby("final_result", as_index=False)
        .size()
        .rename(columns={"size": "student_count"})
    )
    return px.bar(
        chart_data,
        x="final_result",
        y="student_count",
        title="Final Result Distribution",
        labels={"final_result": "Final Result", "student_count": "Students"},
    )


def build_assessment_score_figure(assessments: pd.DataFrame):
    """Build average score by assessment type chart."""
    if assessments.empty:
        return empty_figure("No assessment performance data available")

    chart_data = (
        assessments.groupby("assessment_type", as_index=False)
        .apply(
            lambda group: pd.Series(
                {
                    "average_score": weighted_average(
                        group,
                        value_column="average_score",
                        weight_column="submitted_assessments",
                    )
                }
            ),
            include_groups=False,
        )
        .dropna(subset=["average_score"])
    )
    if chart_data.empty:
        return empty_figure("No assessment score data available")

    return px.bar(
        chart_data,
        x="assessment_type",
        y="average_score",
        title="Average Score By Assessment Type",
        labels={
            "assessment_type": "Assessment Type",
            "average_score": "Average Score",
        },
    )


DATA = load_dashboard_data()

app = Dash(__name__)
app.title = "Learning Analytics Intelligence Platform"

module_options = dropdown_options(DATA["student_module"]["code_module"])
initial_module = module_options[0]["value"] if module_options else None

app.layout = html.Div(
    [
        html.Header(
            [
                html.H1(
                    "Learning Analytics Intelligence Platform",
                    style={"margin": 0, "fontSize": "1.8rem"},
                ),
                html.P(
                    "OULAD dashboard powered by DuckDB and dbt marts.",
                    style={"margin": "0.35rem 0 0", "color": "#52606d"},
                ),
            ],
            style={"marginBottom": "1.5rem"},
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Label("Module", htmlFor="module-dropdown"),
                        dcc.Dropdown(
                            id="module-dropdown",
                            options=module_options,
                            value=initial_module,
                            clearable=True,
                            placeholder="Select module",
                        ),
                    ]
                ),
                html.Div(
                    [
                        html.Label("Presentation", htmlFor="presentation-dropdown"),
                        dcc.Dropdown(
                            id="presentation-dropdown",
                            clearable=True,
                            placeholder="Select presentation",
                        ),
                    ]
                ),
            ],
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(240px, 1fr))",
                "gap": "1rem",
                "marginBottom": "1rem",
            },
        ),
        html.Div(
            id="kpi-cards",
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))",
                "gap": "1rem",
                "marginBottom": "1.25rem",
            },
        ),
        html.Div(
            [
                dcc.Graph(id="clicks-over-time"),
                dcc.Graph(id="active-students-over-time"),
                dcc.Graph(id="final-result-distribution"),
                dcc.Graph(id="assessment-score-by-type"),
            ],
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(360px, 1fr))",
                "gap": "1rem",
            },
        ),
    ],
    style={
        "fontFamily": "Arial, sans-serif",
        "backgroundColor": "#f5f7fa",
        "color": "#1f2933",
        "minHeight": "100vh",
        "padding": "1.5rem",
    },
)


@app.callback(
    Output("presentation-dropdown", "options"),
    Output("presentation-dropdown", "value"),
    Input("module-dropdown", "value"),
)
def update_presentation_options(code_module: str | None):
    """Update presentation options for the selected module."""
    students = filter_by_scope(DATA["student_module"], code_module, None)
    options = dropdown_options(students["code_presentation"])
    value = options[0]["value"] if len(options) == 1 else None
    return options, value


@app.callback(
    Output("kpi-cards", "children"),
    Output("clicks-over-time", "figure"),
    Output("active-students-over-time", "figure"),
    Output("final-result-distribution", "figure"),
    Output("assessment-score-by-type", "figure"),
    Input("module-dropdown", "value"),
    Input("presentation-dropdown", "value"),
)
def update_dashboard(code_module: str | None, code_presentation: str | None):
    """Update KPI cards and figures for the selected scope."""
    students = filter_by_scope(DATA["student_module"], code_module, code_presentation)
    engagement = filter_by_scope(
        DATA["course_engagement_daily"],
        code_module,
        code_presentation,
    )
    assessments = filter_by_scope(
        DATA["assessment_performance"],
        code_module,
        code_presentation,
    )

    return (
        build_kpi_cards(students, engagement, assessments),
        build_clicks_figure(engagement),
        build_active_students_figure(engagement),
        build_final_result_figure(students),
        build_assessment_score_figure(assessments),
    )


if __name__ == "__main__":
    app.run(debug=True)
