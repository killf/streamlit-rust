# Python reference browser traces

These are real black-box observations of the pinned Python Streamlit 1.66.1 application in a browser. They record HTTP requests, WebSocket handshakes and frames, decoded protobuf, DOM observations, and selected screenshots. They are oracle evidence only; the Rust server is not exercised by these files.

Current captures:

- `closed-loop/`: startup, upload, selectbox, slider, checkbox, button pulse.
- `errors/`: malformed CSV, soft-failure amounts, empty data, no-match filter.
- `form/`: typing without submit and one form submit.
- `tabs/`: two concurrent browser tabs with isolated sessions.
- `refresh/`: a page reload; the handshake carries only two entries and a new session id is issued.
- `status/`: the four status elements.  `trace-status.json` holds the four styles and the
  width/icon/title variants; `trace-status-leading.json` was appended later with the
  leading-icon extraction cases and the invalid-parameter semantics; `trace-status-icon-composite.json`
  was appended last with the icon grammar (ZWJ, skin tone, flag, two independent emoji).
  The earlier files were left untouched.
- `data-loop/`: one upload of a CSV to the Python 1.66.1 reference app -- the file URLs exchange, the upload request, the Arrow payload of the table and the Vega-Lite spec of the chart.
- `numeric/`: the four numeric representatives -- one int value, one float value, an int range and a float range -- against the Python 1.66.1 reference app.
- `widgets/`: the selectbox, the slider and the checkbox against the Python 1.66.1 reference app.  The full Element protobuf of each widget, every client widget state, the callback order, the key binding, the disabled widgets and the duplicate-key error.
- `reconnect-ids/`: three WebSocket handshakes that carry a session id in the third subprotocol entry, against the Python 1.66.1 reference app.  A valid but unknown UUID and a non-UUID string each start a new session; the id of a live session resumes it.  No 400, no 409.  The fate of the previously open socket was not observed.
- `reconnect/`: the live socket is closed from the page, the frontend reconnects on its own, and the
  reconnect handshake carries a third subprotocol entry.  Every connection is recorded separately with
  its handshake, its close event and the frames that travelled on it, and a click on the reconnected
  session proves it works: a true trigger and a successful `script_finished` on the new connection.


Regenerate to a temporary directory first, then review before replacing a committed trace:

```powershell
python tests/reference/capture_browser_trace.py --url http://localhost:8601 --scenario closed-loop --out <temporary-path>
```
Superseded captures (replaced, not kept):

- `reconnect/` trace.json sha256:3504db1967797c34d92bf93b197551bbfe822e4982bbddb829b9ede3febc0cb1
- `refresh/` trace.json sha256:34e69133663ec1364ccd7512bfe94e7d93e60275885d8239660691cb95c0fbb7

Both were replaced because they merged the handshakes per tab and kept only the
last one, so they could not show which connection a frame belonged to.

<!-- Legacy chain index: manifest-less captures above stay reachable through the matrix features that cite them. -->
- `buttons/`: frozen browser chain cited by the compatibility matrix under st.download_button, st.feedback, st.link_button, st.menu_button and more.
- `cache/`: frozen browser chain cited by the compatibility matrix under st.cache_data, st.cache_resource.
- `chartlibs/`: frozen browser chain cited by the compatibility matrix under st.altair_chart, st.echarts_chart, st.graphviz_chart, st.mermaid_chart and more.
- `charts/`: frozen browser chain cited by the compatibility matrix under st.area_chart, st.line_chart, st.map, st.scatter_chart.
- `chat/`: frozen browser chain cited by the compatibility matrix under st.chat_input, st.chat_message.
- `colconfig/`: frozen browser chain cited by the compatibility matrix under st.column_config, st.column_config.AreaChartColumn, st.column_config.AudioColumn, st.column_config.BarChartColumn and more.
- `combined/`: frozen browser chain; see the matrix and .codex/compatibility.md for the exact scope.
- `recorder-params/`: the audio-input sample rate and the camera-input default message frozen on both runtimes.
- `json-badge-params/`: json expanded semantics, badge markdown forms with wrap unset, and feedback presets frozen on both runtimes.
- `slider-multi-params/`: datetime-slider microsecond steps, date windows, and indexed multiselect defaults frozen on both runtimes.
- `chat-metric-params/`: emoji avatar typing, the full metric delta rule set, and progress text frozen on both runtimes.
- `button-image-params/`: button/icon/disabled, download URL naming, and the multi-image list overload frozen on both runtimes.
- `temporal-params/`: temporal/slider creation-parameter edges (date bounds/format, select-slider range, time step) frozen on both runtimes.
- `widget-params/`: widget creation-parameter edges (number-input float path, radio index=None/horizontal/captions, text_area bounds, multiselect cap) frozen on both runtimes.
- `combined-interactive/`: the second M7 combined differential — a six-stage real-UI interaction flow (multi-upload, checkbox, selectbox, row selection, button+toast) frozen on both runtimes with per-stage report equality.
- `componenttrigger/`: frozen browser chain cited by the compatibility matrix under st.components.v2.component.
- `componentv2/`: frozen browser chain cited by the compatibility matrix under st.components.v2.component.
- `dataeditor/`: frozen browser chain cited by the compatibility matrix under st.data_editor.
- `datetime/`: frozen browser chain cited by the compatibility matrix under st.datetime_input.
- `display/`: frozen browser chain cited by the compatibility matrix under st.json, st.bottom, st.empty, st.space and more.
- `display2/`: frozen browser chain cited by the compatibility matrix under st.logo, st.pdf, st.skeleton, st.help.
- `elements/`: frozen browser chain cited by the compatibility matrix under st.form, st.form_submit_button, st.bar_chart, st.table and more.
- `execution-j04/`: frozen browser chain cited by the compatibility matrix under st.rerun, st.stop.
- `inputs/`: frozen browser chain cited by the compatibility matrix under st.multiselect, st.number_input, st.radio, st.text_area.
- `layouts/`: frozen browser chain cited by the compatibility matrix under st.dialog, concept.design.layouts-and-containers, st.expander, st.popover and more.
- `media/`: frozen browser chain cited by the compatibility matrix under st.metric, st.audio, st.image, st.progress.
- `navigation/`: frozen browser chain cited by the compatibility matrix under st.navigation, st.Page, st.switch_page, concept.multipage-apps.overview and more.
- `pageconfig/`: frozen browser chain cited by the compatibility matrix under st.set_page_config.
- `pickers/`: frozen browser chain cited by the compatibility matrix under st.audio_input, st.camera_input, st.color_picker, st.date_input and more.
- `presentation/`: frozen browser chain cited by the compatibility matrix under st.balloons, st.spinner, st.toast.
- `queryparams/`: frozen browser chain cited by the compatibility matrix under st.query_params, st.selectbox.
- `temporal/`: frozen browser chain cited by the compatibility matrix under st.slider.
- `textelements/`: frozen browser chain cited by the compatibility matrix under st.components.v1.html, st.components.v1.iframe, st.exception, st.snow and more.
- `video/`: frozen browser chain cited by the compatibility matrix under st.video.
- `writestream/`: frozen browser chain cited by the compatibility matrix under st.write_stream.
