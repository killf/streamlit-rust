//! text/latex/help/divider parameter edges — the frozen text-misc-params
//! reference's calls: plain text, a display formula, the dataframe help
//! string, and the default divider.
use ::streamlit::*;
use streamlit::StreamlitApi;

fn render_layouts(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    let mut cases: Vec<serde_json::Value> = serde_json::from_str(
        r#"[
  {"kind": "markdown", "body": "Markdown default", "kwargs": {}},
  {"kind": "markdown", "body": "Markdown auto", "kwargs": {"width": "auto"}},
  {"kind": "markdown", "body": "Markdown stretch", "kwargs": {"width": "stretch"}},
  {"kind": "markdown", "body": "Markdown content", "kwargs": {"width": "content"}},
  {"kind": "markdown", "body": "Markdown pixels", "kwargs": {"width": 240}},
  {"kind": "markdown", "body": "Markdown help", "kwargs": {"help": "layout help"}},
  {"kind": "markdown", "body": "Markdown center", "kwargs": {"text_alignment": "center"}},
  {"kind": "markdown", "body": "Markdown right", "kwargs": {"text_alignment": "right", "width": "stretch"}},
  {"kind": "markdown", "body": "Markdown justify", "kwargs": {"text_alignment": "justify", "width": 240}},
  {"kind": "caption", "body": "Caption default", "kwargs": {}},
  {"kind": "caption", "body": "Caption content", "kwargs": {"width": "content"}},
  {"kind": "caption", "body": "Caption pixels", "kwargs": {"width": 240}},
  {"kind": "caption", "body": "Caption right help", "kwargs": {"text_alignment": "right", "help": "caption help"}},
  {"kind": "badge", "body": "Badge default", "kwargs": {}},
  {"kind": "badge", "body": "Badge stretch", "kwargs": {"width": "stretch"}},
  {"kind": "badge", "body": "Badge pixels", "kwargs": {"width": 240}},
  {"kind": "badge", "body": "Badge help icon", "kwargs": {"help": "badge help", "icon": "🧊"}}
]"#,
    )?;
    if st.query_params().get("only_widths").as_deref() == Some("true") {
        cases.retain(|case| case["kwargs"].get("text_alignment").is_none());
    }
    st.json(serde_json::json!({"layout_cases": cases}));
    for case in cases {
        let body = case["body"].as_str().ok_or("missing layout body")?;
        let kwargs = &case["kwargs"];
        let width = match kwargs.get("width") {
            None => None,
            Some(value) if value == "auto" => None,
            Some(value) if value == "stretch" => Some(ElementWidth::Stretch),
            Some(value) if value == "content" => Some(ElementWidth::Content),
            Some(value) => Some(ElementWidth::Value(i32::try_from(value.as_i64().ok_or("invalid layout width")?)?)),
        };
        if kwargs.get("text_alignment").is_some() {
            return Err("non-default TextAlignment is not exported by the current Rust API".into());
        }
        let help = kwargs["help"].as_str();
        match case["kind"].as_str() {
            Some("markdown") => {
                let mut options = MarkdownOptions::new(body.to_owned());
                if let Some(width) = width {
                    options = options.width(width);
                }
                if let Some(help) = help {
                    options = options.help(help);
                }
                st.markdown(options);
            }
            Some("caption") => {
                let mut options = CaptionOptions::new(body);
                if let Some(width) = width {
                    options = options.width(width);
                }
                if let Some(help) = help {
                    options = options.help(help);
                }
                st.caption(options);
            }
            Some("badge") => {
                let mut options = BadgeOptions::new(body);
                if let Some(width) = width {
                    options = options.width(width);
                }
                if let Some(help) = help {
                    options = options.help(help);
                }
                if let Some(icon) = kwargs["icon"].as_str() {
                    options = options.icon(icon);
                }
                st.badge(options);
            }
            _ => return Err("invalid layout kind".into()),
        }
    }
    Ok(())
}

fn render_identity(st: &Streamlit) -> Result<(), Box<dyn std::error::Error>> {
    st.title("Element identity controls");
    let alternate = st.checkbox(CheckboxOptions::new("Alternate attributes").key("identity-alternate"))?;

    let help = if alternate { "help B" } else { "help A" };
    st.header(
        HeaderOptions::new("Stable heading")
            .anchor(if alternate { "anchor-b".to_owned() } else { "anchor-a".to_owned() })
            .help(help)
            .divider(if alternate { "red".to_owned() } else { "blue".to_owned() }),
    );
    st.markdown(MarkdownOptions::new("Stable markdown".into()).help(help));
    st.badge(BadgeOptions::new("Stable badge").help(help));

    if alternate {
        st.caption("Same style text");
    } else {
        st.markdown("Same style text");
    }

    st.button(ButtonOptions::new("Action").key("identity-action").disabled(alternate).help(help).icon(if alternate { "✅" } else { "🧊" }).width(ElementWidth::Content));
    st.caption(format!("alternate={alternate}"));
    Ok(())
}

fn render(st: &Streamlit) {
    if st.query_params().get("case").as_deref() == Some("layouts") {
        if let Err(error) = render_layouts(st) {
            st.write(format!("Layout error: {error}"));
        }
        return;
    }
    if st.query_params().get("case").as_deref() == Some("identity") {
        if let Err(error) = render_identity(st) {
            st.write(format!("Element identity error: {error}"));
        }
        return;
    }
    st.title("Text misc parameter edges");
    st.text("plain body");
    st.latex(r"\int_0^1 x^2 dx");
    st.help(HelpOptions::new(
        "Display a dataframe as an interactive table.\n\nThis command works with a wide variety of collection-like and\ndataframe-like object types.\n\nTo disable data export (CSV download and clipboard copy), set the\n``client.disableDataExport`` configuration option to ``True``.\n\nParameters\n----------\ndata : dataframe-like, collection-like, or None\n    The data to display.\n\n    Dataframe-like objects include dataframe and series objects from\n    popular libraries like Dask, Modin, Numpy, pandas, Polars, PyArrow,\n    Snowpark, Xarray, and more. You can use database cursors and\n    clients that comply with the\n    `Python Database API Specification v2.0 (PEP 249)\n    <https://peps.python.org/pep-0249/>`_. Additionally, you can use\n    anything that supports the `Python dataframe interchange protocol\n    <https://data-apis.org/dataframe-protocol/latest/>`_.\n\n    For example, you can use the following:\n\n    - ``pandas.DataFrame``, ``pandas.Series``, ``pandas.Index``,\n      ``pandas.Styler``, and ``pandas.Array``\n    - ``polars.DataFrame``, ``polars.LazyFrame``, and ``polars.Series``\n    - ``snowflake.snowpark.dataframe.DataFrame``,\n      ``snowflake.snowpark.table.Table``\n\n    If a data type is not recognized, Streamlit will convert the object\n    to a ``pandas.DataFrame`` or ``pyarrow.Table`` using a\n    ``.to_pandas()`` or ``.to_arrow()`` method, respectively, if\n    available.\n\n    If ``data`` is a ``pandas.Styler``, it will be used to style its\n    underlying ``pandas.DataFrame``. Streamlit supports custom cell\n    values, colors, and font weights. It does not support some of the\n    more exotic styling options, like bar charts, hovering, and\n    captions. For these options, use column configuration where an\n    equivalent exists (for example, ``BarChartColumn`` or\n    ``ProgressColumn`` instead of Styler bars), or use ``st.table``\n    for small, static tables that need fuller Pandas Styler support.\n    Text and number formatting from ``column_config`` always takes\n    precedence over text and number formatting from ``pandas.Styler``.\n\n    Collection-like objects include all Python-native ``Collection``\n    types, such as ``dict``, ``list``, and ``set``.\n\n    If ``data`` is ``None``, Streamlit renders an empty table.\n\nwidth : \"stretch\", \"content\", or int\n    The width of the dataframe element. This can be one of the following:\n\n    - ``\"stretch\"`` (default): The width of the element matches the\n      width of the parent container.\n    - ``\"content\"``: The width of the element matches the width of its\n      content, but doesn't exceed the width of the parent container.\n    - An integer specifying the width in pixels: The element has a\n      fixed width. If the specified width is greater than the width of\n      the parent container, the width of the element matches the width\n      of the parent container.\n\nheight : \"auto\", \"content\", \"stretch\", or int\n    The height of the dataframe element. This can be one of the following:\n\n    - ``\"auto\"`` (default): Streamlit sets the height to show at most\n      ten rows.\n    - ``\"content\"``: The height of the element matches the height of\n      its content. The height is capped at 10,000 pixels to prevent\n      performance issues with very large dataframes.\n    - ``\"stretch\"``: The height of the element expands to fill the\n      available vertical space in its parent container. When multiple\n      elements with stretch height are in the same container, they\n      share the available vertical space evenly. The dataframe will\n      maintain a minimum height to display up to three rows, but\n      otherwise won't exceed the available height in its parent\n      container.\n    - An integer specifying the height in pixels: The element has a\n      fixed height.\n\n    Vertical scrolling within the dataframe element is enabled when the\n    height does not accommodate all rows.\n\nuse_container_width : bool\n    Whether to override ``width`` with the width of the parent\n    container. If this is ``True`` (default), Streamlit sets the width\n    of the dataframe to match the width of the parent container. If\n    this is ``False``, Streamlit sets the dataframe's width according\n    to ``width``.\n\n    .. deprecated::\n        ``use_container_width`` is deprecated and will be removed in a\n        future release. For ``use_container_width=True``, use\n        ``width=\"stretch\"``.\n\nhide_index : bool or None\n    Whether to hide the index column(s). If ``hide_index`` is ``None``\n    (default), the visibility of index columns is automatically\n    determined based on the data and other configurations.\n\ncolumn_order : Iterable[str] or None\n    The ordered list of columns to display. If this is ``None``\n    (default), Streamlit displays all columns in the order inherited\n    from the underlying data structure. If this is a list, the\n    indicated columns will display in the order they appear within the\n    list. Columns may be omitted or repeated within the list.\n\n    For example, ``column_order=(\"col2\", \"col1\")`` will display\n    ``\"col2\"`` first, followed by ``\"col1\"``, and will hide all other\n    non-index columns.\n\n    ``column_order`` does not accept positional column indices and\n    can't move the index column(s).\n\n    .. note::\n        Columns omitted from ``column_order`` are hidden by default\n        but can still be shown by the user via the column visibility\n        menu in the table toolbar. If a column contains sensitive data\n        that should not be exposed to the user, remove it from the\n        data before passing it to the function.\n\ncolumn_config : dict or None\n    Configuration to customize how columns are displayed. If this is\n    ``None`` (default), columns are styled based on the underlying data\n    type of each column.\n\n    Column configuration can modify column names, visibility, type,\n    width, format, and more. If this is a dictionary, the keys are\n    column names (strings) and/or positional column indices (integers),\n    and the values are one of the following:\n\n    - ``None`` to hide the column. Hidden columns can still be shown\n      by the user via the table toolbar.\n    - A string to set the display label of the column.\n    - One of the column types defined under ``st.column_config``. For\n      example, to show a column as dollar amounts, use\n      ``st.column_config.NumberColumn(\"Dollar values\", format=\"$ %d\")``.\n      See more info on the available column types and config options\n      `here <https://docs.streamlit.io/develop/api-reference/data/st.column_config>`_.\n\n    To configure the index column(s), use ``\"_index\"`` as the column\n    name, or use a positional column index where ``0`` refers to the\n    first index column.\n\nkey : str, int, or None\n    An optional string to use for giving this element a stable\n    identity. If this is ``None`` (default), the element's identity\n    will be determined based on the values of the other parameters.\n\n    If selections are activated, a key lets you read or update the\n    selection state via ``st.session_state[key]``. The value in\n    Session State must be a dictionary consistent with the\n    ``DataframeState`` schema. For more details, see `Widget behavior\n    <https://docs.streamlit.io/develop/concepts/architecture/widget-behavior>`_.\n\n    Additionally, if ``key`` is provided, it will be used as a\n    CSS class name prefixed with ``st-key-``.\n\non_select : \"ignore\" or \"rerun\" or callable\n    How the dataframe should respond to user selection events. This\n    controls whether or not the dataframe behaves like an input widget.\n    ``on_select`` can be one of the following:\n\n    - ``\"ignore\"`` (default): Streamlit will not react to any selection\n      events in the dataframe. The dataframe will not behave like an\n      input widget.\n\n    - ``\"rerun\"``: Streamlit will rerun the app when the user selects\n      rows, columns, or cells in the dataframe. In this case,\n      ``st.dataframe`` will return the selection data as a dictionary.\n\n    - A ``callable``: Streamlit will rerun the app and execute the\n      ``callable`` as a callback function before the rest of the app.\n      In this case, ``st.dataframe`` will return the selection data\n      as a dictionary.\n\nselection_mode : \"single-row\", \"single-row-required\", \"multi-row\",             \"single-column\", \"multi-column\", \"single-cell\", \"multi-cell\",             or Iterable of these\n    The types of selections Streamlit should allow when selections are\n    enabled with ``on_select``. This can be one of the following:\n\n    - \"multi-row\" (default): Multiple rows can be selected at a time.\n    - \"single-row\": Only one row can be selected at a time.\n    - \"single-row-required\": Exactly one row must always be selected\n      (radio-like behavior). Auto-selects the first row if no default\n      is given.\n    - \"multi-column\": Multiple columns can be selected at a time.\n    - \"single-column\": Only one column can be selected at a time.\n    - \"multi-cell\": A rectangular range of cells can be selected.\n    - \"single-cell\": Only one cell can be selected at a time.\n    - An ``Iterable`` of the above options: The table will allow\n      selection based on the modes specified. For example, to allow the\n      user to select multiple rows and multiple cells, use\n      ``[\"multi-row\", \"multi-cell\"]``.\n\n    When column selections are enabled, column sorting is disabled.\n\nselection_default : dict or None\n    The default selection state to apply on first render when selections\n    are activated and no prior selection is stored. This uses the same\n    schema as ``st.session_state[key]`` for selections, for example:\n    ``{\"selection\": {\"rows\": [0, 2]}}``.\n\n    ``selection_default`` is only applied when ``on_select`` is not\n    ``\"ignore\"``. It does not override user selections on subsequent\n    runs, and multi-cell selections cannot be set programmatically.\n\nrow_height : int or None\n    The height of each row in the dataframe in pixels. If ``row_height``\n    is ``None`` (default), Streamlit will use a default row height,\n    which fits one line of text.\n\nplaceholder : str or None\n    The text that should be shown for missing values. If this is\n    ``None`` (default), missing values are displayed as \"None\". To\n    leave a cell empty, use an empty string (``\"\"``). Other common\n    values are ``\"null\"``, ``\"NaN\"`` and ``\"-\"``.\n\nlazy : bool or None\n    Whether to load rows lazily from the app server instead of sending\n    the full dataset to the browser. When rows are loaded lazily,\n    Streamlit sends only the rows the user is viewing and fetches more\n    as they scroll or sort. This is useful for datasets that are too\n    large to send to the browser all at once. It can also make your app\n    faster on reruns, since far less data needs to be transferred from\n    the app server to the client (browser). This can be one of the\n    following:\n\n    - ``None`` (default): Streamlit chooses automatically. In-memory\n      ``pandas`` and ``polars`` dataframes and ``pyarrow.Table`` objects\n      are loaded lazily when they have more than 150,000 rows.\n      Unevaluated objects, such as a Polars ``LazyFrame``, are loaded\n      lazily when they have more than 10,000 rows. Everything else is\n      loaded eagerly, including the capped preview for unsupported\n      unevaluated objects.\n    - ``True``: Always load rows lazily. For inputs that support lazy\n      access natively (for example, a Polars ``LazyFrame``), Streamlit\n      reads rows directly from the source. Other supported inputs are\n      held in the app server's memory and served in chunks. Small\n      datasets (1,000 rows or fewer) are still loaded eagerly as an\n      optimization. If lazy loading is incompatible with the data or the\n      other parameters (for example, dataframes with multi-level,\n      ``MultiIndex``, column headers), Streamlit raises a\n      ``StreamlitAPIException``.\n    - ``False``: Never load rows lazily. Streamlit loads data eagerly\n      and uses the capped preview for unevaluated data objects.\n\n    .. note::\n        When rows are loaded lazily, search, CSV download, selections\n        (``on_select``), and ``pandas.Styler`` styling are not\n        supported. Server-side sorting is supported. To use these\n        features, set ``lazy=False``.\n\nalt : str or None\n    A short, plain-text accessible name for the dataframe. If this is\n    ``None`` (default), the grid has no element-level accessible name.\n    Cell values remain available through the grid's own accessibility\n    tree.\n\n    An empty or whitespace-only string is treated the same as ``None``.\n\n    Prefer naming what the data is (for example, \"Top 20 customers by\n    revenue\") rather than pasting cell contents. This is a short name\n    for findability, not a full text alternative for the table.\n\nReturns\n-------\nelement or DataframeState\n    If ``on_select`` is ``\"ignore\"`` (default), this command returns an\n    internal placeholder for the dataframe element. Otherwise, this\n    command returns a ``DataframeState`` object. This object is\n    dictionary-like and supports both key and attribute notation. To\n    use this type in an annotation, import it from\n    ``streamlit.typing``.\n\nExamples\n--------\n**Example 1: Display a dataframe**\n\n>>> import pandas as pd\n>>> import streamlit as st\n>>> from numpy.random import default_rng as rng\n>>>\n>>> df = pd.DataFrame(\n...     rng(0).standard_normal((50, 20)), columns=(\"col %d\" % i for i in range(20))\n... )\n>>>\n>>> st.dataframe(df)\n\n.. output::\n   https://doc-dataframe.streamlit.app/\n   height: 500px\n\n**Example 2: Use Pandas Styler**\n\nYou can also pass a Pandas Styler object to change the style of\nthe rendered DataFrame:\n\n>>> import pandas as pd\n>>> import streamlit as st\n>>> from numpy.random import default_rng as rng\n>>>\n>>> df = pd.DataFrame(\n...     rng(0).standard_normal((10, 20)), columns=(\"col %d\" % i for i in range(20))\n... )\n>>>\n>>> st.dataframe(df.style.highlight_max(axis=0))\n\n.. output::\n   https://doc-dataframe1.streamlit.app/\n   height: 500px\n\n**Example 3: Use column configuration**\n\nYou can customize a dataframe via ``column_config``, ``hide_index``, or ``column_order``.\n\n>>> import pandas as pd\n>>> import streamlit as st\n>>> from numpy.random import default_rng as rng\n>>>\n>>> df = pd.DataFrame(\n...     {\n...         \"name\": [\"Roadmap\", \"Extras\", \"Issues\"],\n...         \"url\": [\n...             \"https://roadmap.streamlit.app\",\n...             \"https://extras.streamlit.app\",\n...             \"https://issues.streamlit.app\",\n...         ],\n...         \"stars\": rng(0).integers(0, 1000, size=3),\n...         \"views_history\": rng(0).integers(0, 5000, size=(3, 30)).tolist(),\n...     }\n... )\n>>>\n>>> st.dataframe(\n...     df,\n...     column_config={\n...         \"name\": \"App name\",\n...         \"stars\": st.column_config.NumberColumn(\n...             \"Github Stars\",\n...             help=\"Number of stars on GitHub\",\n...             format=\"%d ⭐\",\n...         ),\n...         \"url\": st.column_config.LinkColumn(\"App URL\"),\n...         \"views_history\": st.column_config.LineChartColumn(\n...             \"Views (past 30 days)\", y_min=0, y_max=5000\n...         ),\n...     },\n...     hide_index=True,\n... )\n\n.. output::\n   https://doc-dataframe-config.streamlit.app/\n   height: 350px\n\n**Example 4: Customize your index**\n\nYou can use column configuration to format your index.\n\n>>> from datetime import datetime, date\n>>> import numpy as np\n>>> import pandas as pd\n>>> import streamlit as st\n>>>\n>>> @st.cache_data\n>>> def load_data():\n>>>     year = datetime.now().year\n>>>     df = pd.DataFrame(\n...         {\n...             \"Date\": [date(year, month, 1) for month in range(1, 4)],\n...             \"Total\": np.random.randint(1000, 5000, size=3),\n...         }\n...     )\n>>>     df.set_index(\"Date\", inplace=True)\n>>>     return df\n>>>\n>>> df = load_data()\n>>> config = {\n...     \"_index\": st.column_config.DateColumn(\"Month\", format=\"MMM YYYY\"),\n...     \"Total\": st.column_config.NumberColumn(\"Total ($)\"),\n... }\n>>>\n>>> st.dataframe(df, column_config=config)\n\n.. output::\n   https://doc-dataframe-config-index.streamlit.app/\n   height: 225px",
        "method",
    )
    .name("st.dataframe")
    .value("streamlit.delta_generator.ArrowMixin.dataframe(data: 'Data' = None, width: 'Width' = 'stretch', height: \"Height | Literal['auto']\" = 'auto', *, use_container_width: 'bool | None' = None, hide_index: 'bool | None' = None, column_order: 'Iterable[str] | None' = None, column_config: 'ColumnConfigMappingInput | None' = None, key: 'Key | None' = None, on_select: \"Literal['ignore', 'rerun'] | WidgetCallback\" = 'ignore', selection_mode: 'SelectionMode | Iterable[SelectionMode]' = 'multi-row', selection_default: 'DataframeStateInput | DataframeState | None' = None, row_height: 'int | None' = None, placeholder: 'str | None' = None, lazy: 'bool | None' = None, alt: 'str | None' = None) -> 'DeltaGenerator | DataframeState'"));
    st.divider();
}

#[main(host = "127.0.0.1", port = 8606)]
async fn main(st: &Streamlit) {
    render(st);
}
