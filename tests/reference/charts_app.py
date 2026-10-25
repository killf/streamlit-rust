"""Charts reference fixture: native line, area, scatter charts and one map."""

import pandas as pd
import streamlit as st

series = pd.DataFrame({"value": [2, 1, 3]})
st.line_chart(series)

wide = pd.DataFrame({"alpha": [1, 2, 3], "beta": [3, 2, 1]})
st.area_chart(wide)

points = pd.DataFrame({"x": [1, 2, 3], "y": [3, 1, 2]})
st.scatter_chart(points, x="x", y="y")

places = pd.DataFrame({"lat": [40.7, 41.0], "lon": [-74.0, -73.9]})
st.map(places)
