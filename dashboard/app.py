"""Dash dashboard for the Learning Analytics Intelligence Platform."""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dash_table, dcc, html


DASHBOARD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DASHBOARD_DIR.parent
WAREHOUSE_PATH = PROJECT_ROOT / "data" / "warehouse" / "laip.duckdb"

MART_TABLES = {
    "student_module": "dim_student_module",
    "course_engagement_daily": "fct_course_engagement_daily",
    "assessment_performance": "fct_assessment_performance",
    "student_success_features": "mart_student_success_features",
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
    "student_success_features": [
        "code_module",
        "code_presentation",
        "id_student",
        "risk_band",
        "risk_score_simple",
        "final_result",
        "is_withdrawn",
        "total_clicks",
        "active_days",
        "has_declining_engagement",
        "average_score",
        "submitted_assessments",
        "average_submission_delay_days",
        "is_low_engagement",
    ],
}

RISK_BAND_ORDER = ["Low", "Medium", "High"]
RISK_BAND_SORT_ORDER = {"High": 0, "Medium": 1, "Low": 2}
DASHBOARD_COLORS = {
    "primary": "#2563eb",
    "secondary": "#0f766e",
    "success": "#16a34a",
    "warning": "#d97706",
    "danger": "#dc2626",
    "muted": "#64748b",
    "background": "#f8fafc",
    "surface": "#ffffff",
    "border": "#d9e2ec",
    "grid": "#e5e7eb",
    "text": "#1f2933",
}
RISK_BAND_COLORS = {
    "Low": DASHBOARD_COLORS["success"],
    "Medium": DASHBOARD_COLORS["warning"],
    "High": DASHBOARD_COLORS["danger"],
}
FINAL_RESULT_COLORS = {
    "Distinction": DASHBOARD_COLORS["secondary"],
    "Pass": DASHBOARD_COLORS["success"],
    "Fail": DASHBOARD_COLORS["warning"],
    "Withdrawn": DASHBOARD_COLORS["danger"],
}
STUDENT_RISK_COLUMNS = [
    "id_student",
    "code_module",
    "code_presentation",
    "risk_band",
    "risk_score_simple",
    "final_result",
    "is_withdrawn",
    "total_clicks",
    "active_days",
    "has_declining_engagement",
    "average_score",
    "submitted_assessments",
    "average_submission_delay_days",
]
GRAPH_GRID_STYLE = {
    "display": "grid",
    "gridTemplateColumns": "repeat(auto-fit, minmax(360px, 1fr))",
    "gap": "1rem",
}
SECTION_STYLE = {"marginTop": "1.5rem"}


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


def apply_chart_layout(figure, hovermode: str = "closest"):
    """Apply a consistent, lightweight dashboard chart style."""
    figure.update_layout(
        template="plotly_white",
        paper_bgcolor=DASHBOARD_COLORS["surface"],
        plot_bgcolor=DASHBOARD_COLORS["surface"],
        font={"color": DASHBOARD_COLORS["text"], "size": 12},
        title={"font": {"size": 18}, "x": 0.02, "xanchor": "left"},
        margin={"l": 56, "r": 28, "t": 72, "b": 52},
        hovermode=hovermode,
        legend_title_text="",
    )
    figure.update_xaxes(
        showgrid=False,
        linecolor=DASHBOARD_COLORS["border"],
        title_font={"size": 12},
        tickfont={"size": 11},
    )
    figure.update_yaxes(
        showgrid=True,
        gridcolor=DASHBOARD_COLORS["grid"],
        zeroline=False,
        linecolor=DASHBOARD_COLORS["border"],
        title_font={"size": 12},
        tickfont={"size": 11},
    )
    return figure


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
    return apply_chart_layout(figure)


def section_header(title: str, note: str) -> html.Div:
    """Render a consistent dashboard section heading."""
    return html.Div(
        [
            html.H2(
                title,
                style={
                    "fontSize": "1.35rem",
                    "margin": "0 0 0.35rem",
                },
            ),
            html.P(
                note,
                style={
                    "margin": "0 0 0.85rem",
                    "color": DASHBOARD_COLORS["muted"],
                    "lineHeight": "1.45",
                },
            ),
        ]
    )


def format_number(value: float | int | None) -> str:
    """Format dashboard numbers for KPI cards."""
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.0f}"


def format_percent(value: float | None) -> str:
    """Format dashboard percentages for KPI cards."""
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.1f}%"


def format_decimal(value: float | None) -> str:
    """Format score-like values for KPI cards."""
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.1f}"


def normalize_bool_value(value):
    """Normalize boolean-like mart values for analytics and labels."""
    if pd.isna(value):
        return pd.NA
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def numeric_mean(data_frame: pd.DataFrame, column: str) -> float | None:
    """Calculate a mean after removing null and non-numeric values."""
    if data_frame.empty or column not in data_frame.columns:
        return None

    values = pd.to_numeric(data_frame[column], errors="coerce").dropna()
    if values.empty:
        return None

    return float(values.mean())


def boolean_rate(data_frame: pd.DataFrame, column: str) -> float | None:
    """Calculate the percent of true values in a boolean-like column."""
    if data_frame.empty or column not in data_frame.columns:
        return None

    values = data_frame[column].map(normalize_bool_value).dropna()
    if values.empty:
        return None

    return float(values.astype(bool).mean() * 100)


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
    success_features: pd.DataFrame,
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
    high_risk_students = (
        success_features[success_features["risk_band"] == "High"]
        if "risk_band" in success_features.columns
        else pd.DataFrame()
    )
    high_risk_count = len(high_risk_students)
    high_risk_rate = (
        high_risk_count / len(success_features) * 100 if len(success_features) else None
    )
    high_risk_withdrawal_rate = boolean_rate(high_risk_students, "is_withdrawn")
    high_risk_average_score = numeric_mean(high_risk_students, "average_score")

    kpis = [
        ("Total Enrollments", format_number(total_enrollments)),
        ("Withdrawal Rate", format_percent(withdrawal_rate)),
        ("Total Clicks", format_number(total_clicks)),
        (
            "Average Assessment Score",
            f"{average_score:.1f}" if average_score is not None else "N/A",
        ),
        ("High-Risk Students", format_number(high_risk_count)),
        ("High-Risk Rate", format_percent(high_risk_rate)),
        (
            "High-Risk Withdrawal Rate",
            format_percent(high_risk_withdrawal_rate),
        ),
        ("High-Risk Average Score", format_decimal(high_risk_average_score)),
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
            "border": f"1px solid {DASHBOARD_COLORS['border']}",
            "borderRadius": "8px",
            "padding": "1rem",
            "backgroundColor": DASHBOARD_COLORS["surface"],
        },
    )


def build_clicks_figure(engagement: pd.DataFrame):
    """Build total clicks trend chart."""
    if engagement.empty:
        return empty_figure("No engagement data available")

    chart_data = engagement.sort_values("activity_date")
    figure = px.line(
        chart_data,
        x="activity_date",
        y="total_clicks",
        title="Daily Course Clicks",
        labels={"activity_date": "Course Day", "total_clicks": "Total Clicks"},
        color_discrete_sequence=[DASHBOARD_COLORS["primary"]],
    )
    return apply_chart_layout(figure, hovermode="x unified")


def build_active_students_figure(engagement: pd.DataFrame):
    """Build active students trend chart."""
    if engagement.empty:
        return empty_figure("No active student data available")

    chart_data = engagement.sort_values("activity_date")
    figure = px.line(
        chart_data,
        x="activity_date",
        y="active_students",
        title="Daily Active Students",
        labels={
            "activity_date": "Course Day",
            "active_students": "Active Students",
        },
        color_discrete_sequence=[DASHBOARD_COLORS["secondary"]],
    )
    return apply_chart_layout(figure, hovermode="x unified")


def build_final_result_figure(students: pd.DataFrame):
    """Build final result distribution chart."""
    if students.empty:
        return empty_figure("No student outcome data available")

    chart_data = (
        students.groupby("final_result", as_index=False)
        .size()
        .rename(columns={"size": "student_count"})
    )
    figure = px.bar(
        chart_data,
        x="final_result",
        y="student_count",
        title="Final Result Distribution",
        labels={"final_result": "Final Result", "student_count": "Students"},
        color="final_result",
        color_discrete_map=FINAL_RESULT_COLORS,
    )
    figure.update_layout(showlegend=False)
    return apply_chart_layout(figure)


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

    figure = px.bar(
        chart_data,
        x="assessment_type",
        y="average_score",
        title="Average Assessment Score by Assessment Type",
        labels={
            "assessment_type": "Assessment Type",
            "average_score": "Average Score",
        },
        color_discrete_sequence=[DASHBOARD_COLORS["primary"]],
    )
    return apply_chart_layout(figure)


def build_learning_journey_funnel_figure(
    students: pd.DataFrame,
    success_features: pd.DataFrame,
):
    """Build the selected cohort learning journey funnel."""
    required_columns = {
        "total_clicks",
        "submitted_assessments",
        "final_result",
    }
    if success_features.empty or not required_columns.issubset(
        success_features.columns
    ):
        return empty_figure("No student-success data available for the funnel")

    total_clicks = pd.to_numeric(success_features["total_clicks"], errors="coerce")
    submitted_assessments = pd.to_numeric(
        success_features["submitted_assessments"],
        errors="coerce",
    )
    enrolled_students = len(students) if not students.empty else len(success_features)
    active_students = int((total_clicks.fillna(0) > 0).sum())
    submitted_students = int((submitted_assessments.fillna(0) > 0).sum())
    passed_students = int(
        success_features["final_result"].isin(["Pass", "Distinction"]).sum()
    )

    chart_data = pd.DataFrame(
        {
            "stage": [
                "Enrolled students",
                "Active in VLE",
                "Submitted assessment",
                "Passed or distinction",
            ],
            "student_count": [
                enrolled_students,
                active_students,
                submitted_students,
                passed_students,
            ],
        }
    )

    figure = px.funnel(
        chart_data,
        x="student_count",
        y="stage",
        title="Learning Journey Funnel",
        labels={"stage": "Learning Journey Stage", "student_count": "Students"},
        color="stage",
        color_discrete_map={
            "Enrolled students": DASHBOARD_COLORS["primary"],
            "Active in VLE": DASHBOARD_COLORS["secondary"],
            "Submitted assessment": DASHBOARD_COLORS["warning"],
            "Passed or distinction": DASHBOARD_COLORS["success"],
        },
    )
    figure.update_traces(texttemplate="%{value:,.0f}", textposition="inside")
    figure.update_layout(showlegend=False)
    return apply_chart_layout(figure)


def build_withdrawal_by_declining_engagement_figure(success_features: pd.DataFrame):
    """Build withdrawal rate by declining engagement chart."""
    required_columns = {"has_declining_engagement", "is_withdrawn"}
    if success_features.empty or not required_columns.issubset(
        success_features.columns
    ):
        return empty_figure("No student-success data available")

    chart_data = success_features.copy()
    engagement_labels = {
        False: "No declining engagement",
        True: "Declining engagement",
    }
    chart_data["engagement_pattern"] = (
        chart_data["has_declining_engagement"]
        .map(normalize_bool_value)
        .map(engagement_labels)
    )
    chart_data["withdrawn_flag"] = chart_data["is_withdrawn"].map(normalize_bool_value)
    chart_data = chart_data.dropna(subset=["engagement_pattern", "withdrawn_flag"])
    if chart_data.empty:
        return empty_figure("No withdrawal data available by engagement pattern")

    chart_data["withdrawn_flag"] = chart_data["withdrawn_flag"].astype(bool)
    grouped = (
        chart_data.groupby("engagement_pattern", as_index=False)["withdrawn_flag"]
        .mean()
        .rename(columns={"withdrawn_flag": "withdrawal_rate"})
    )
    grouped["withdrawal_rate"] = grouped["withdrawal_rate"] * 100

    figure = px.bar(
        grouped,
        x="engagement_pattern",
        y="withdrawal_rate",
        title="Withdrawal Rate by Declining Engagement",
        labels={
            "engagement_pattern": "Engagement Pattern",
            "withdrawal_rate": "Withdrawal Rate",
        },
        category_orders={"engagement_pattern": list(engagement_labels.values())},
        color="engagement_pattern",
        color_discrete_map={
            "No declining engagement": DASHBOARD_COLORS["muted"],
            "Declining engagement": DASHBOARD_COLORS["danger"],
        },
    )
    figure.update_layout(showlegend=False)
    figure.update_yaxes(ticksuffix="%")
    return apply_chart_layout(figure)


def build_score_by_low_engagement_figure(success_features: pd.DataFrame):
    """Build average score by low-engagement status chart."""
    required_columns = {"is_low_engagement", "average_score"}
    if success_features.empty or not required_columns.issubset(
        success_features.columns
    ):
        return empty_figure("No student-success data available")

    chart_data = success_features.copy()
    engagement_labels = {
        False: "Not low engagement",
        True: "Low engagement",
    }
    chart_data["engagement_group"] = (
        chart_data["is_low_engagement"].map(normalize_bool_value).map(engagement_labels)
    )
    chart_data["average_score"] = pd.to_numeric(
        chart_data["average_score"],
        errors="coerce",
    )
    chart_data = chart_data.dropna(subset=["engagement_group", "average_score"])
    if chart_data.empty:
        return empty_figure("No assessment scores available by engagement group")

    grouped = chart_data.groupby("engagement_group", as_index=False)[
        "average_score"
    ].mean()

    figure = px.bar(
        grouped,
        x="engagement_group",
        y="average_score",
        title="Average Score by Engagement Group",
        labels={
            "engagement_group": "Engagement Group",
            "average_score": "Average Score",
        },
        category_orders={"engagement_group": list(engagement_labels.values())},
        color="engagement_group",
        color_discrete_map={
            "Not low engagement": DASHBOARD_COLORS["secondary"],
            "Low engagement": DASHBOARD_COLORS["danger"],
        },
    )
    figure.update_layout(showlegend=False)
    return apply_chart_layout(figure)


def build_risk_band_count_figure(success_features: pd.DataFrame):
    """Build student count by rule-based risk band chart."""
    if success_features.empty or "risk_band" not in success_features.columns:
        return empty_figure("No risk band data available")

    chart_data = success_features.dropna(subset=["risk_band"]).copy()
    if chart_data.empty:
        return empty_figure("No risk band data available")

    chart_data["risk_band"] = pd.Categorical(
        chart_data["risk_band"],
        categories=RISK_BAND_ORDER,
        ordered=True,
    )
    chart_data = chart_data.dropna(subset=["risk_band"])
    grouped = (
        chart_data.groupby("risk_band", observed=True)
        .size()
        .reset_index(name="student_count")
    )

    figure = px.bar(
        grouped,
        x="risk_band",
        y="student_count",
        title="Student Count by Rule-Based Risk Band",
        labels={"risk_band": "Risk Band", "student_count": "Students"},
        category_orders={"risk_band": RISK_BAND_ORDER},
        color="risk_band",
        color_discrete_map=RISK_BAND_COLORS,
    )
    figure.update_layout(showlegend=False)
    return apply_chart_layout(figure)


def build_withdrawal_by_risk_band_figure(success_features: pd.DataFrame):
    """Build withdrawal rate by rule-based risk band chart."""
    required_columns = {"risk_band", "is_withdrawn"}
    if success_features.empty or not required_columns.issubset(
        success_features.columns
    ):
        return empty_figure("No risk band withdrawal data available")

    chart_data = success_features.dropna(subset=["risk_band"]).copy()
    chart_data["risk_band"] = pd.Categorical(
        chart_data["risk_band"],
        categories=RISK_BAND_ORDER,
        ordered=True,
    )
    chart_data["withdrawn_flag"] = chart_data["is_withdrawn"].map(normalize_bool_value)
    chart_data = chart_data.dropna(subset=["risk_band", "withdrawn_flag"])
    if chart_data.empty:
        return empty_figure("No risk band withdrawal data available")

    chart_data["withdrawn_flag"] = chart_data["withdrawn_flag"].astype(bool)
    grouped = (
        chart_data.groupby("risk_band", observed=True)["withdrawn_flag"]
        .mean()
        .reset_index(name="withdrawal_rate")
    )
    grouped["withdrawal_rate"] = grouped["withdrawal_rate"] * 100

    figure = px.bar(
        grouped,
        x="risk_band",
        y="withdrawal_rate",
        title="Withdrawal Rate by Rule-Based Risk Band",
        labels={"risk_band": "Risk Band", "withdrawal_rate": "Withdrawal Rate"},
        category_orders={"risk_band": RISK_BAND_ORDER},
        color="risk_band",
        color_discrete_map=RISK_BAND_COLORS,
    )
    figure.update_layout(showlegend=False)
    figure.update_yaxes(ticksuffix="%")
    return apply_chart_layout(figure)


def format_bool_label(value) -> str:
    """Format boolean-like values for the student risk table."""
    normalized = normalize_bool_value(value)
    if pd.isna(normalized):
        return "N/A"
    return "Yes" if normalized else "No"


def build_student_risk_table(success_features: pd.DataFrame):
    """Build a table of the highest-risk student-module attempts."""
    if success_features.empty:
        return html.Div(
            "No student-success feature data available for the selected scope.",
            style={"color": "#52606d", "padding": "1rem"},
        )

    missing_columns = [
        column for column in STUDENT_RISK_COLUMNS if column not in success_features
    ]
    if missing_columns:
        return html.Div(
            "Student-success mart is missing expected columns for the risk table.",
            style={"color": "#52606d", "padding": "1rem"},
        )

    table_data = success_features.copy()
    table_data["_risk_score_sort"] = pd.to_numeric(
        table_data["risk_score_simple"],
        errors="coerce",
    ).fillna(-1)
    table_data["_risk_band_sort"] = (
        table_data["risk_band"].map(RISK_BAND_SORT_ORDER).fillna(99)
    )
    table_data["_total_clicks_sort"] = pd.to_numeric(
        table_data["total_clicks"],
        errors="coerce",
    ).fillna(float("inf"))
    table_data["_average_score_sort"] = pd.to_numeric(
        table_data["average_score"],
        errors="coerce",
    ).fillna(float("inf"))

    table_data = table_data.sort_values(
        [
            "_risk_score_sort",
            "_risk_band_sort",
            "_total_clicks_sort",
            "_average_score_sort",
        ],
        ascending=[False, True, True, True],
    ).head(50)

    display_data = table_data[STUDENT_RISK_COLUMNS].copy()
    for column in [
        "risk_score_simple",
        "total_clicks",
        "active_days",
        "submitted_assessments",
    ]:
        display_data[column] = pd.to_numeric(
            display_data[column],
            errors="coerce",
        ).round(0)

    for column in ["average_score", "average_submission_delay_days"]:
        display_data[column] = pd.to_numeric(
            display_data[column],
            errors="coerce",
        ).round(1)

    display_data["is_withdrawn"] = display_data["is_withdrawn"].map(format_bool_label)
    display_data["has_declining_engagement"] = display_data[
        "has_declining_engagement"
    ].map(format_bool_label)
    display_data = display_data.where(pd.notna(display_data), None)

    table_columns = [
        {"name": "Anonymized Student ID", "id": "id_student"},
        {"name": "Module", "id": "code_module"},
        {"name": "Presentation", "id": "code_presentation"},
        {"name": "Risk Band", "id": "risk_band"},
        {"name": "Risk Score", "id": "risk_score_simple"},
        {"name": "Final Result", "id": "final_result"},
        {"name": "Withdrawn", "id": "is_withdrawn"},
        {"name": "Total Clicks", "id": "total_clicks"},
        {"name": "Active Days", "id": "active_days"},
        {"name": "Declining Engagement", "id": "has_declining_engagement"},
        {"name": "Average Score", "id": "average_score"},
        {"name": "Submitted Assessments", "id": "submitted_assessments"},
        {"name": "Avg Submission Delay", "id": "average_submission_delay_days"},
    ]

    return dash_table.DataTable(
        columns=table_columns,
        data=display_data.to_dict("records"),
        page_size=10,
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "fontFamily": "Arial, sans-serif",
            "fontSize": "0.85rem",
            "padding": "0.55rem",
            "textAlign": "left",
            "minWidth": "90px",
        },
        style_header={
            "backgroundColor": "#f0f4f8",
            "fontWeight": "700",
            "border": f"1px solid {DASHBOARD_COLORS['border']}",
        },
        style_data={
            "backgroundColor": DASHBOARD_COLORS["surface"],
            "border": "1px solid #e4e7eb",
        },
        style_data_conditional=[
            {
                "if": {"filter_query": '{risk_band} = "High"'},
                "backgroundColor": "#fff5f5",
            },
        ],
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
                    style={
                        "margin": "0.35rem 0 0",
                        "color": DASHBOARD_COLORS["muted"],
                    },
                ),
            ],
            style={"marginBottom": "1.5rem"},
        ),
        html.Section(
            [
                section_header(
                    "Course Overview",
                    "Filter the dashboard by module and presentation, then review "
                    "the core enrollment, outcome, engagement, and high-risk KPIs.",
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
                                html.Label(
                                    "Presentation",
                                    htmlFor="presentation-dropdown",
                                ),
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
                    },
                ),
            ],
            style=SECTION_STYLE,
        ),
        html.Section(
            [
                section_header(
                    "Engagement & Assessment Trends",
                    "Track course activity, active learners, outcomes, and "
                    "assessment performance using dashboard-ready mart tables.",
                ),
                html.Div(
                    [
                        dcc.Graph(id="clicks-over-time"),
                        dcc.Graph(id="active-students-over-time"),
                        dcc.Graph(id="final-result-distribution"),
                        dcc.Graph(id="assessment-score-by-type"),
                    ],
                    style=GRAPH_GRID_STYLE,
                ),
            ],
            style=SECTION_STYLE,
        ),
        html.Section(
            [
                section_header(
                    "Learning Journey Funnel",
                    "Summarize how the selected cohort moves from enrollment "
                    "through activity, assessment submission, and successful outcome.",
                ),
                dcc.Graph(id="learning-journey-funnel"),
            ],
            style=SECTION_STYLE,
        ),
        html.Section(
            [
                section_header(
                    "Student Success Signals",
                    "Compare rule-based student-success signals against withdrawal "
                    "and assessment outcomes for the selected cohort.",
                ),
                html.Ul(
                    [
                        html.Li(
                            "Risk bands are rule-based analytical indicators, "
                            "not validated predictive ML predictions."
                        ),
                        html.Li("Student identifiers are anonymized OULAD IDs."),
                        html.Li(
                            "Declining engagement is measured within each student's "
                            "observed activity window."
                        ),
                    ],
                    style={
                        "color": DASHBOARD_COLORS["muted"],
                        "lineHeight": "1.45",
                        "marginTop": 0,
                    },
                ),
                html.Div(
                    [
                        dcc.Graph(id="withdrawal-rate-by-declining-engagement"),
                        dcc.Graph(id="average-score-by-low-engagement"),
                        dcc.Graph(id="risk-band-distribution"),
                        dcc.Graph(id="withdrawal-rate-by-risk-band"),
                    ],
                    style=GRAPH_GRID_STYLE,
                ),
            ],
            style=SECTION_STYLE,
        ),
        html.Section(
            [
                section_header(
                    "Highest-Risk Student-Module Attempts",
                    "The table shows up to 50 anonymized student-module attempts "
                    "with the strongest combination of rule-based risk signals.",
                ),
                html.Div(
                    id="student-risk-table",
                    style={
                        "border": f"1px solid {DASHBOARD_COLORS['border']}",
                        "borderRadius": "8px",
                        "backgroundColor": DASHBOARD_COLORS["surface"],
                    },
                ),
            ],
            style=SECTION_STYLE,
        ),
    ],
    style={
        "fontFamily": "Arial, sans-serif",
        "backgroundColor": DASHBOARD_COLORS["background"],
        "color": DASHBOARD_COLORS["text"],
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
    Output("learning-journey-funnel", "figure"),
    Output("withdrawal-rate-by-declining-engagement", "figure"),
    Output("average-score-by-low-engagement", "figure"),
    Output("risk-band-distribution", "figure"),
    Output("withdrawal-rate-by-risk-band", "figure"),
    Output("student-risk-table", "children"),
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
    success_features = filter_by_scope(
        DATA["student_success_features"],
        code_module,
        code_presentation,
    )

    return (
        build_kpi_cards(students, engagement, assessments, success_features),
        build_clicks_figure(engagement),
        build_active_students_figure(engagement),
        build_final_result_figure(students),
        build_assessment_score_figure(assessments),
        build_learning_journey_funnel_figure(students, success_features),
        build_withdrawal_by_declining_engagement_figure(success_features),
        build_score_by_low_engagement_figure(success_features),
        build_risk_band_count_figure(success_features),
        build_withdrawal_by_risk_band_figure(success_features),
        build_student_risk_table(success_features),
    )


if __name__ == "__main__":
    app.run(debug=True)
