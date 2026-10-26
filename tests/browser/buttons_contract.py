"""The strict button-family contract: journey-buttons-v1.

This criterion judges the observation the committed collector
(buttons_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-26 with the official frontend and recorded in .codex/compatibility.md
(Button family). The collector states no verdict; this module owns it:

* st.toggle is a checkbox element with the TOGGLE style (default true only
  when declared), content width, at consecutive main slots;
* st.feedback is a feedback element with only the style enum set (STARS),
  unselected on load;
* st.pills / st.segmented_control are button_group elements: Option content
  lists, SINGLE_SELECT omitted / MULTI_SELECT set, PILLS / SEGMENTED_CONTROL
  styles, index defaults only when declared;
* st.pagination carries num_pages, default and max_visible_pages, never a
  stray value;
* st.menu_button carries label, option strings and the button type;
* st.download_button carries the content-addressed /media/<hash>.txt URL
  of the declared bytes (same digest on both sides);
* st.link_button carries its keyed id and ignore_rerun=true (the reference's
  on_click="ignore" default); st.page_link carries page, label, external;
* the five committed interactions report exactly the measured widget states
  (toggle bool, single pill label, pagination int, feedback string index,
  menu string trigger) and the settled DOM shows every control.

Widget ids are judged modulo the $$ID digest segment; the browser's
widget-state serialization order is normalized (hash order differs between
sessions); at most one leading main-container add_block at [0] is the Rust
runtime's documented divergence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

BUTTONS_CASE = "buttons-page"
BUTTONS_CONTRACT = "journey-buttons-v1"

BUTTONS_STAGES = [
    '01-load',
    '02-toggle',
    '03-pills',
    '04-pagination',
    '05-feedback',
    '06-menu'
]

# Per stage: the normalized frame timeline and the DOM projection.
BUTTONS_TIMELINE = {
    '01-load': [
        {
            'kind': 'rerun',
            'states': []
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'checkbox',
            'widget': {
                'label': 'Night mode',
                'labelVisibility': {},
                'type': 'TOGGLE'
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'checkbox',
            'widget': {
                'label': 'Sound',
                'default': True,
                'labelVisibility': {},
                'type': 'TOGGLE'
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'feedback',
            'widget': {
                'type': 'STARS'
            },
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'feedback',
            'widget': {},
            'path': [
                0,
                3
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'low'
                    },
                    {
                        'content': 'medium'
                    },
                    {
                        'content': 'high'
                    }
                ],
                'style': 'PILLS',
                'label': 'Priority',
                'labelVisibility': {}
            },
            'path': [
                0,
                4
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'alpha'
                    },
                    {
                        'content': 'beta'
                    },
                    {
                        'content': 'gamma'
                    }
                ],
                'default': [
                    0
                ],
                'clickMode': 'MULTI_SELECT',
                'style': 'PILLS',
                'label': 'Tags',
                'labelVisibility': {}
            },
            'path': [
                0,
                5
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'grid'
                    },
                    {
                        'content': 'list'
                    }
                ],
                'default': [
                    0
                ],
                'label': 'View',
                'labelVisibility': {}
            },
            'path': [
                0,
                6
            ]
        },
        {
            'kind': 'pagination',
            'widget': {
                'numPages': 10,
                'default': 1,
                'maxVisiblePages': 7
            },
            'path': [
                0,
                7
            ]
        },
        {
            'kind': 'markdown',
            'body': 'page=1',
            'path': [
                0,
                8
            ]
        },
        {
            'kind': 'menu_button',
            'widget': {
                'label': 'Export',
                'options': [
                    'CSV',
                    'JSON'
                ],
                'type': 'secondary'
            },
            'path': [
                0,
                9
            ]
        },
        {
            'kind': 'download_button',
            'widget': {
                'label': 'Save report',
                'url': '/media/<hash>.txt',
                'type': 'secondary'
            },
            'path': [
                0,
                10
            ]
        },
        {
            'kind': 'link_button',
            'widget': {
                'label': 'Docs',
                'url': 'https://docs.streamlit.io',
                'type': 'secondary',
                'ignoreRerun': True
            },
            'path': [
                0,
                11
            ]
        },
        {
            'kind': 'page_link',
            'widget': {
                'page': 'https://example.com',
                'label': 'Example site',
                'external': True
            },
            'path': [
                0,
                12
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '02-toggle': [
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$ID-None',
                    'value_field': 'bool_value',
                    'value': True
                },
                {
                    'id': '$$ID-None',
                    'value_field': 'string_value',
                    'value': ''
                },
                {
                    'id': '$$ID-night',
                    'value_field': 'bool_value',
                    'value': True
                },
                {
                    'id': '$$ID-pager',
                    'value_field': 'int_value',
                    'value': 1
                },
                {
                    'id': '$$ID-priority',
                    'value_field': 'string_array_value',
                    'value': {}
                },
                {
                    'id': '$$ID-rate',
                    'value_field': 'string_value',
                    'value': ''
                },
                {
                    'id': '$$ID-tags',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['alpha']"
                    }
                },
                {
                    'id': '$$ID-view',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['grid']"
                    }
                }
            ]
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'checkbox',
            'widget': {
                'label': 'Night mode',
                'labelVisibility': {},
                'type': 'TOGGLE'
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'checkbox',
            'widget': {
                'label': 'Sound',
                'default': True,
                'labelVisibility': {},
                'type': 'TOGGLE'
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'feedback',
            'widget': {
                'type': 'STARS'
            },
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'feedback',
            'widget': {},
            'path': [
                0,
                3
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'low'
                    },
                    {
                        'content': 'medium'
                    },
                    {
                        'content': 'high'
                    }
                ],
                'style': 'PILLS',
                'label': 'Priority',
                'labelVisibility': {}
            },
            'path': [
                0,
                4
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'alpha'
                    },
                    {
                        'content': 'beta'
                    },
                    {
                        'content': 'gamma'
                    }
                ],
                'default': [
                    0
                ],
                'clickMode': 'MULTI_SELECT',
                'style': 'PILLS',
                'label': 'Tags',
                'labelVisibility': {}
            },
            'path': [
                0,
                5
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'grid'
                    },
                    {
                        'content': 'list'
                    }
                ],
                'default': [
                    0
                ],
                'label': 'View',
                'labelVisibility': {}
            },
            'path': [
                0,
                6
            ]
        },
        {
            'kind': 'pagination',
            'widget': {
                'numPages': 10,
                'default': 1,
                'maxVisiblePages': 7
            },
            'path': [
                0,
                7
            ]
        },
        {
            'kind': 'markdown',
            'body': 'page=1',
            'path': [
                0,
                8
            ]
        },
        {
            'kind': 'menu_button',
            'widget': {
                'label': 'Export',
                'options': [
                    'CSV',
                    'JSON'
                ],
                'type': 'secondary'
            },
            'path': [
                0,
                9
            ]
        },
        {
            'kind': 'download_button',
            'widget': {
                'label': 'Save report',
                'url': '/media/<hash>.txt',
                'type': 'secondary'
            },
            'path': [
                0,
                10
            ]
        },
        {
            'kind': 'link_button',
            'widget': {
                'label': 'Docs',
                'url': 'https://docs.streamlit.io',
                'type': 'secondary',
                'ignoreRerun': True
            },
            'path': [
                0,
                11
            ]
        },
        {
            'kind': 'page_link',
            'widget': {
                'page': 'https://example.com',
                'label': 'Example site',
                'external': True
            },
            'path': [
                0,
                12
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '03-pills': [
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$ID-None',
                    'value_field': 'bool_value',
                    'value': True
                },
                {
                    'id': '$$ID-None',
                    'value_field': 'string_value',
                    'value': ''
                },
                {
                    'id': '$$ID-night',
                    'value_field': 'bool_value',
                    'value': True
                },
                {
                    'id': '$$ID-pager',
                    'value_field': 'int_value',
                    'value': 1
                },
                {
                    'id': '$$ID-priority',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['high']"
                    }
                },
                {
                    'id': '$$ID-rate',
                    'value_field': 'string_value',
                    'value': ''
                },
                {
                    'id': '$$ID-tags',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['alpha']"
                    }
                },
                {
                    'id': '$$ID-view',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['grid']"
                    }
                }
            ]
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'checkbox',
            'widget': {
                'label': 'Night mode',
                'labelVisibility': {},
                'type': 'TOGGLE'
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'checkbox',
            'widget': {
                'label': 'Sound',
                'default': True,
                'labelVisibility': {},
                'type': 'TOGGLE'
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'feedback',
            'widget': {
                'type': 'STARS'
            },
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'feedback',
            'widget': {},
            'path': [
                0,
                3
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'low'
                    },
                    {
                        'content': 'medium'
                    },
                    {
                        'content': 'high'
                    }
                ],
                'style': 'PILLS',
                'label': 'Priority',
                'labelVisibility': {}
            },
            'path': [
                0,
                4
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'alpha'
                    },
                    {
                        'content': 'beta'
                    },
                    {
                        'content': 'gamma'
                    }
                ],
                'default': [
                    0
                ],
                'clickMode': 'MULTI_SELECT',
                'style': 'PILLS',
                'label': 'Tags',
                'labelVisibility': {}
            },
            'path': [
                0,
                5
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'grid'
                    },
                    {
                        'content': 'list'
                    }
                ],
                'default': [
                    0
                ],
                'label': 'View',
                'labelVisibility': {}
            },
            'path': [
                0,
                6
            ]
        },
        {
            'kind': 'pagination',
            'widget': {
                'numPages': 10,
                'default': 1,
                'maxVisiblePages': 7
            },
            'path': [
                0,
                7
            ]
        },
        {
            'kind': 'markdown',
            'body': 'page=1',
            'path': [
                0,
                8
            ]
        },
        {
            'kind': 'menu_button',
            'widget': {
                'label': 'Export',
                'options': [
                    'CSV',
                    'JSON'
                ],
                'type': 'secondary'
            },
            'path': [
                0,
                9
            ]
        },
        {
            'kind': 'download_button',
            'widget': {
                'label': 'Save report',
                'url': '/media/<hash>.txt',
                'type': 'secondary'
            },
            'path': [
                0,
                10
            ]
        },
        {
            'kind': 'link_button',
            'widget': {
                'label': 'Docs',
                'url': 'https://docs.streamlit.io',
                'type': 'secondary',
                'ignoreRerun': True
            },
            'path': [
                0,
                11
            ]
        },
        {
            'kind': 'page_link',
            'widget': {
                'page': 'https://example.com',
                'label': 'Example site',
                'external': True
            },
            'path': [
                0,
                12
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '04-pagination': [
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$ID-None',
                    'value_field': 'bool_value',
                    'value': True
                },
                {
                    'id': '$$ID-None',
                    'value_field': 'string_value',
                    'value': ''
                },
                {
                    'id': '$$ID-night',
                    'value_field': 'bool_value',
                    'value': True
                },
                {
                    'id': '$$ID-pager',
                    'value_field': 'int_value',
                    'value': 2
                },
                {
                    'id': '$$ID-priority',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['high']"
                    }
                },
                {
                    'id': '$$ID-rate',
                    'value_field': 'string_value',
                    'value': ''
                },
                {
                    'id': '$$ID-tags',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['alpha']"
                    }
                },
                {
                    'id': '$$ID-view',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['grid']"
                    }
                }
            ]
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'checkbox',
            'widget': {
                'label': 'Night mode',
                'labelVisibility': {},
                'type': 'TOGGLE'
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'checkbox',
            'widget': {
                'label': 'Sound',
                'default': True,
                'labelVisibility': {},
                'type': 'TOGGLE'
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'feedback',
            'widget': {
                'type': 'STARS'
            },
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'feedback',
            'widget': {},
            'path': [
                0,
                3
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'low'
                    },
                    {
                        'content': 'medium'
                    },
                    {
                        'content': 'high'
                    }
                ],
                'style': 'PILLS',
                'label': 'Priority',
                'labelVisibility': {}
            },
            'path': [
                0,
                4
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'alpha'
                    },
                    {
                        'content': 'beta'
                    },
                    {
                        'content': 'gamma'
                    }
                ],
                'default': [
                    0
                ],
                'clickMode': 'MULTI_SELECT',
                'style': 'PILLS',
                'label': 'Tags',
                'labelVisibility': {}
            },
            'path': [
                0,
                5
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'grid'
                    },
                    {
                        'content': 'list'
                    }
                ],
                'default': [
                    0
                ],
                'label': 'View',
                'labelVisibility': {}
            },
            'path': [
                0,
                6
            ]
        },
        {
            'kind': 'pagination',
            'widget': {
                'numPages': 10,
                'default': 1,
                'maxVisiblePages': 7
            },
            'path': [
                0,
                7
            ]
        },
        {
            'kind': 'markdown',
            'body': 'page=2',
            'path': [
                0,
                8
            ]
        },
        {
            'kind': 'menu_button',
            'widget': {
                'label': 'Export',
                'options': [
                    'CSV',
                    'JSON'
                ],
                'type': 'secondary'
            },
            'path': [
                0,
                9
            ]
        },
        {
            'kind': 'download_button',
            'widget': {
                'label': 'Save report',
                'url': '/media/<hash>.txt',
                'type': 'secondary'
            },
            'path': [
                0,
                10
            ]
        },
        {
            'kind': 'link_button',
            'widget': {
                'label': 'Docs',
                'url': 'https://docs.streamlit.io',
                'type': 'secondary',
                'ignoreRerun': True
            },
            'path': [
                0,
                11
            ]
        },
        {
            'kind': 'page_link',
            'widget': {
                'page': 'https://example.com',
                'label': 'Example site',
                'external': True
            },
            'path': [
                0,
                12
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '05-feedback': [
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$ID-None',
                    'value_field': 'bool_value',
                    'value': True
                },
                {
                    'id': '$$ID-None',
                    'value_field': 'string_value',
                    'value': ''
                },
                {
                    'id': '$$ID-night',
                    'value_field': 'bool_value',
                    'value': True
                },
                {
                    'id': '$$ID-pager',
                    'value_field': 'int_value',
                    'value': 2
                },
                {
                    'id': '$$ID-priority',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['high']"
                    }
                },
                {
                    'id': '$$ID-rate',
                    'value_field': 'string_value',
                    'value': '2'
                },
                {
                    'id': '$$ID-tags',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['alpha']"
                    }
                },
                {
                    'id': '$$ID-view',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['grid']"
                    }
                }
            ]
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'checkbox',
            'widget': {
                'label': 'Night mode',
                'labelVisibility': {},
                'type': 'TOGGLE'
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'checkbox',
            'widget': {
                'label': 'Sound',
                'default': True,
                'labelVisibility': {},
                'type': 'TOGGLE'
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'feedback',
            'widget': {
                'type': 'STARS'
            },
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'feedback',
            'widget': {},
            'path': [
                0,
                3
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'low'
                    },
                    {
                        'content': 'medium'
                    },
                    {
                        'content': 'high'
                    }
                ],
                'style': 'PILLS',
                'label': 'Priority',
                'labelVisibility': {}
            },
            'path': [
                0,
                4
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'alpha'
                    },
                    {
                        'content': 'beta'
                    },
                    {
                        'content': 'gamma'
                    }
                ],
                'default': [
                    0
                ],
                'clickMode': 'MULTI_SELECT',
                'style': 'PILLS',
                'label': 'Tags',
                'labelVisibility': {}
            },
            'path': [
                0,
                5
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'grid'
                    },
                    {
                        'content': 'list'
                    }
                ],
                'default': [
                    0
                ],
                'label': 'View',
                'labelVisibility': {}
            },
            'path': [
                0,
                6
            ]
        },
        {
            'kind': 'pagination',
            'widget': {
                'numPages': 10,
                'default': 1,
                'maxVisiblePages': 7
            },
            'path': [
                0,
                7
            ]
        },
        {
            'kind': 'markdown',
            'body': 'page=2',
            'path': [
                0,
                8
            ]
        },
        {
            'kind': 'menu_button',
            'widget': {
                'label': 'Export',
                'options': [
                    'CSV',
                    'JSON'
                ],
                'type': 'secondary'
            },
            'path': [
                0,
                9
            ]
        },
        {
            'kind': 'download_button',
            'widget': {
                'label': 'Save report',
                'url': '/media/<hash>.txt',
                'type': 'secondary'
            },
            'path': [
                0,
                10
            ]
        },
        {
            'kind': 'link_button',
            'widget': {
                'label': 'Docs',
                'url': 'https://docs.streamlit.io',
                'type': 'secondary',
                'ignoreRerun': True
            },
            'path': [
                0,
                11
            ]
        },
        {
            'kind': 'page_link',
            'widget': {
                'page': 'https://example.com',
                'label': 'Example site',
                'external': True
            },
            'path': [
                0,
                12
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ],
    '06-menu': [
        {
            'kind': 'rerun',
            'states': [
                {
                    'id': '$$ID-None',
                    'value_field': 'bool_value',
                    'value': True
                },
                {
                    'id': '$$ID-None',
                    'value_field': 'string_value',
                    'value': ''
                },
                {
                    'id': '$$ID-export',
                    'value_field': 'string_trigger_value',
                    'value': {
                        'data': 'CSV'
                    }
                },
                {
                    'id': '$$ID-night',
                    'value_field': 'bool_value',
                    'value': True
                },
                {
                    'id': '$$ID-pager',
                    'value_field': 'int_value',
                    'value': 2
                },
                {
                    'id': '$$ID-priority',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['high']"
                    }
                },
                {
                    'id': '$$ID-rate',
                    'value_field': 'string_value',
                    'value': '2'
                },
                {
                    'id': '$$ID-tags',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['alpha']"
                    }
                },
                {
                    'id': '$$ID-view',
                    'value_field': 'string_array_value',
                    'value': {
                        'data': "['grid']"
                    }
                }
            ]
        },
        {
            'kind': 'new_session'
        },
        {
            'kind': 'session_status_changed'
        },
        {
            'kind': 'checkbox',
            'widget': {
                'label': 'Night mode',
                'labelVisibility': {},
                'type': 'TOGGLE'
            },
            'path': [
                0,
                0
            ]
        },
        {
            'kind': 'checkbox',
            'widget': {
                'label': 'Sound',
                'default': True,
                'labelVisibility': {},
                'type': 'TOGGLE'
            },
            'path': [
                0,
                1
            ]
        },
        {
            'kind': 'feedback',
            'widget': {
                'type': 'STARS'
            },
            'path': [
                0,
                2
            ]
        },
        {
            'kind': 'feedback',
            'widget': {},
            'path': [
                0,
                3
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'low'
                    },
                    {
                        'content': 'medium'
                    },
                    {
                        'content': 'high'
                    }
                ],
                'style': 'PILLS',
                'label': 'Priority',
                'labelVisibility': {}
            },
            'path': [
                0,
                4
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'alpha'
                    },
                    {
                        'content': 'beta'
                    },
                    {
                        'content': 'gamma'
                    }
                ],
                'default': [
                    0
                ],
                'clickMode': 'MULTI_SELECT',
                'style': 'PILLS',
                'label': 'Tags',
                'labelVisibility': {}
            },
            'path': [
                0,
                5
            ]
        },
        {
            'kind': 'button_group',
            'widget': {
                'options': [
                    {
                        'content': 'grid'
                    },
                    {
                        'content': 'list'
                    }
                ],
                'default': [
                    0
                ],
                'label': 'View',
                'labelVisibility': {}
            },
            'path': [
                0,
                6
            ]
        },
        {
            'kind': 'pagination',
            'widget': {
                'numPages': 10,
                'default': 1,
                'maxVisiblePages': 7
            },
            'path': [
                0,
                7
            ]
        },
        {
            'kind': 'markdown',
            'body': 'page=2',
            'path': [
                0,
                8
            ]
        },
        {
            'kind': 'menu_button',
            'widget': {
                'label': 'Export',
                'options': [
                    'CSV',
                    'JSON'
                ],
                'type': 'secondary'
            },
            'path': [
                0,
                9
            ]
        },
        {
            'kind': 'download_button',
            'widget': {
                'label': 'Save report',
                'url': '/media/<hash>.txt',
                'type': 'secondary'
            },
            'path': [
                0,
                10
            ]
        },
        {
            'kind': 'link_button',
            'widget': {
                'label': 'Docs',
                'url': 'https://docs.streamlit.io',
                'type': 'secondary',
                'ignoreRerun': True
            },
            'path': [
                0,
                11
            ]
        },
        {
            'kind': 'page_link',
            'widget': {
                'page': 'https://example.com',
                'label': 'Example site',
                'external': True
            },
            'path': [
                0,
                12
            ]
        },
        {
            'kind': 'script_finished'
        },
        {
            'kind': 'session_status_changed'
        }
    ]
}

BUTTONS_DOMS = {
    '01-load': {
        'buttons': [
            'Deploy',
            '',
            'star',
            'star',
            'star',
            'star',
            'star',
            'thumb_up',
            'thumb_down',
            'low',
            'medium',
            'high',
            'alpha',
            'beta',
            'gamma',
            'grid',
            'list',
            'chevron_left',
            '1',
            '2',
            '3',
            '4',
            '5',
            '10',
            'chevron_right',
            'Exportexpand_more',
            'Save report'
        ],
        'checkboxes': [
            'Night mode',
            'Sound'
        ],
        'markdowns': [],
        'exceptions': []
    },
    '02-toggle': {
        'buttons': [
            'Deploy',
            '',
            'star',
            'star',
            'star',
            'star',
            'star',
            'thumb_up',
            'thumb_down',
            'low',
            'medium',
            'high',
            'alpha',
            'beta',
            'gamma',
            'grid',
            'list',
            'chevron_left',
            '1',
            '2',
            '3',
            '4',
            '5',
            '10',
            'chevron_right',
            'Exportexpand_more',
            'Save report'
        ],
        'checkboxes': [
            'Night mode',
            'Sound'
        ],
        'markdowns': [],
        'exceptions': []
    },
    '03-pills': {
        'buttons': [
            'Deploy',
            '',
            'star',
            'star',
            'star',
            'star',
            'star',
            'thumb_up',
            'thumb_down',
            'low',
            'medium',
            'high',
            'alpha',
            'beta',
            'gamma',
            'grid',
            'list',
            'chevron_left',
            '1',
            '2',
            '3',
            '4',
            '5',
            '10',
            'chevron_right',
            'Exportexpand_more',
            'Save report'
        ],
        'checkboxes': [
            'Night mode',
            'Sound'
        ],
        'markdowns': [],
        'exceptions': []
    },
    '04-pagination': {
        'buttons': [
            'Deploy',
            '',
            'star',
            'star',
            'star',
            'star',
            'star',
            'thumb_up',
            'thumb_down',
            'low',
            'medium',
            'high',
            'alpha',
            'beta',
            'gamma',
            'grid',
            'list',
            'chevron_left',
            '1',
            '2',
            '3',
            '4',
            '5',
            '10',
            'chevron_right',
            'Exportexpand_more',
            'Save report'
        ],
        'checkboxes': [
            'Night mode',
            'Sound'
        ],
        'markdowns': [],
        'exceptions': []
    },
    '05-feedback': {
        'buttons': [
            'Deploy',
            '',
            '',
            '',
            '',
            'star',
            'star',
            'thumb_up',
            'thumb_down',
            'low',
            'medium',
            'high',
            'alpha',
            'beta',
            'gamma',
            'grid',
            'list',
            'chevron_left',
            '1',
            '2',
            '3',
            '4',
            '5',
            '10',
            'chevron_right',
            'Exportexpand_more',
            'Save report'
        ],
        'checkboxes': [
            'Night mode',
            'Sound'
        ],
        'markdowns': [],
        'exceptions': []
    },
    '06-menu': {
        'buttons': [
            'Deploy',
            '',
            '',
            '',
            '',
            'star',
            'star',
            'thumb_up',
            'thumb_down',
            'low',
            'medium',
            'high',
            'alpha',
            'beta',
            'gamma',
            'grid',
            'list',
            'chevron_left',
            '1',
            '2',
            '3',
            '4',
            '5',
            '10',
            'chevron_right',
            'Exportexpand_more',
            'Save report'
        ],
        'checkboxes': [
            'Night mode',
            'Sound'
        ],
        'markdowns': [],
        'exceptions': []
    }
}

BUTTONS_SOURCE_PINS = {
    "python": [
    'tests/reference/buttons_app.py',
    '301325fef04f99504bd2577edbeed14991e0b2335170cae7a0d4d99807f1530d'
],
    "native": [
    'streamlit/examples/buttons.rs',
    '79817da724ca2b6d57f9615b955d9acc6219d30ce7a357026b605c426a705f4d'
],
}

BUTTONS_REQUIRED = (
    "contract", "stage_set", "source_pin", "timeline", "toggle_wire",
    "feedback_wire", "group_wire", "pagination_wire", "menu_wire",
    "download_wire", "link_wire", "page_link_wire", "interaction_wires",
    "dom_projection", "no_exceptions", "finishes", "png_sources",
)

_ID_SUB = re.compile(r"\$\$ID-[0-9a-f]{32}-")
_MEDIA_SUB = re.compile(r"/media/[0-9a-f]{32}")


def _record(checks, name, ok, expected, actual):
    checks.append({"step": BUTTONS_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _normalized_state(state):
    state = {**state, "id": _ID_SUB.sub("$$ID-", state.get("id") or "")}
    state.pop("value_full", None)
    return state


def _sorted_states(states):
    return sorted((_normalized_state(state) for state in states), key=lambda state: (state["id"], state.get("value_field", "")))


def _timeline(stage):
    """The stage's normalized frames, the optional leading main container
    peeled off (the Rust side emits exactly one, the reference none)."""
    out = []
    stripped = 0
    for frame in stage.get("new_frames") or []:
        summary = frame.get("summary") or {}
        kind = summary.get("type")
        if kind == "delta":
            delta = summary.get("delta") or {}
            inner = delta.get("type")
            _need(inner in ("new_element", "add_block"), f"unexpected delta kind {inner!r}")
            if inner == "add_block" and (delta.get("path") or None) == [0] and (delta.get("block") or {}).get("id") == "main_container":
                stripped += 1
                _need(stripped <= 1, "more than one leading main-container block")
                continue
            if inner == "add_block":
                _need(False, f"unexpected block {sorted(delta.get('block') or {})}")
            name = delta.get("element")
            if name in ("checkbox", "feedback", "button_group", "pagination", "menu_button", "link_button", "page_link", "download_button"):
                widget = {key: value for key, value in (delta.get("widget") or {}).items() if key != "id"}
                if isinstance(widget.get("url"), str):
                    widget["url"] = _MEDIA_SUB.sub("/media/<hash>", widget["url"])
                # The widget dict may be legitimately empty (an all-default
                # message, like the thumbs feedback); absence means the
                # collector failed to record it.
                _need(delta.get("widget") is not None, f"{name} delta lacks its full widget")
                out.append({"kind": name, "widget": widget, "path": delta.get("path")})
            else:
                out.append({"kind": name, "body": delta.get("body"), "path": delta.get("path")})
        elif kind == "rerun_script":
            rerun = summary.get("rerun_script") or {}
            out.append({"kind": "rerun", "states": _sorted_states(rerun.get("widget_states") or [])})
        elif kind in ("new_session", "session_status_changed", "script_finished"):
            out.append({"kind": kind})
        else:
            _need(False, f"unexpected frame kind {kind!r}")
    return out


def _entries(stage_timeline, kind):
    return [entry for entry in stage_timeline if entry["kind"] == kind]


def buttons_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 button-family wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 button-family wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == BUTTONS_CASE and observation.get("contract") == BUTTONS_CONTRACT,
              "missing versioned buttons contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(BUTTONS_STAGES),
              f"stages must be exactly the {len(BUTTONS_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        source = observation.get("source") or {}
        side = "python" if observation.get("scope") == "PYTHON SIDE ONLY" else "native"
        path, pinned = BUTTONS_SOURCE_PINS[side]
        _need(source.get("file") == path and source.get("sha256") == pinned,
              f"driven source is not the pinned {path} of this contract")
        mark("source_pin")

        timelines = {stage["name"]: _timeline(stage) for stage in stages}
        for name in BUTTONS_STAGES:
            _need(timelines[name] == BUTTONS_TIMELINE[name],
                  f"stage {name} frame timeline differs from the measured wire ({len(timelines[name])} frames)")
        mark("timeline")

        load = timelines["01-load"]
        toggles = _entries(load, "checkbox")
        _need(len(toggles) == 2, f"the load must carry exactly two toggles, got {len(toggles)}")
        _need(toggles[0]["widget"] == {"label": "Night mode", "labelVisibility": {}, "type": "TOGGLE"},
              "the first toggle is the unkeyed-off Night mode")
        _need(toggles[1]["widget"] == {"label": "Sound", "default": True, "labelVisibility": {}, "type": "TOGGLE"},
              "the second toggle declares its true default")
        _need([entry["path"] for entry in toggles] == [[0, 0], [0, 1]], "the toggles sit at consecutive slots")
        mark("toggle_wire")

        feedbacks = _entries(load, "feedback")
        _need(len(feedbacks) == 2, f"the load must carry exactly two feedbacks, got {len(feedbacks)}")
        _need(feedbacks[0]["widget"] == {"type": "STARS"}, "the stars feedback carries only its style")
        _need(feedbacks[1]["widget"] == {}, "the thumbs feedback carries no field at all")
        mark("feedback_wire")

        groups = _entries(load, "button_group")
        _need(len(groups) == 3, f"the load must carry three button groups, got {len(groups)}")
        _need(groups[0]["widget"] == {"options": [{"content": "low"}, {"content": "medium"}, {"content": "high"}],
                                       "style": "PILLS", "label": "Priority", "labelVisibility": {}},
              "the single-select pills carry their content options and no default")
        _need(groups[1]["widget"] == {"options": [{"content": "alpha"}, {"content": "beta"}, {"content": "gamma"}],
                                        "default": [0], "clickMode": "MULTI_SELECT", "style": "PILLS",
                                        "label": "Tags", "labelVisibility": {}},
              "the multi-select pills carry their index default and mode")
        _need(groups[2]["widget"] == {"options": [{"content": "grid"}, {"content": "list"}], "default": [0],
                                       "label": "View", "labelVisibility": {}},
              "the segmented control omits its default style enum")
        mark("group_wire")

        paginations = _entries(load, "pagination")
        _need(len(paginations) == 1 and paginations[0]["widget"] == {"numPages": 10, "default": 1, "maxVisiblePages": 7},
              "the pagination carries its count, default and visible-page cap")
        mark("pagination_wire")

        menus = _entries(load, "menu_button")
        _need(len(menus) == 1 and menus[0]["widget"] == {"label": "Export", "options": ["CSV", "JSON"], "type": "secondary"},
              "the menu button carries its label, options and type")
        mark("menu_wire")

        downloads = _entries(load, "download_button")
        _need(len(downloads) == 1 and downloads[0]["widget"] == {"label": "Save report", "url": "/media/<hash>.txt", "type": "secondary"},
              "the download button carries the content-addressed media URL")
        mark("download_wire")

        links = _entries(load, "link_button")
        _need(len(links) == 1 and links[0]["widget"] == {"label": "Docs", "url": "https://docs.streamlit.io", "type": "secondary", "ignoreRerun": True},
              "the link button defaults to ignore_rerun navigation")
        mark("link_wire")

        page_links = _entries(load, "page_link")
        _need(len(page_links) == 1 and page_links[0]["widget"] == {"page": "https://example.com", "label": "Example site", "external": True},
              "the external page link carries its url, label and external flag")
        mark("page_link_wire")

        # The five committed interactions: each stage's rerun reports the
        # measured set of widget states (order-normalized) and each rerun
        # keeps streaming the full element list.
        for name in ("02-toggle", "03-pills", "04-pagination", "05-feedback", "06-menu"):
            reruns = _entries(timelines[name], "rerun")
            expected = _entries(BUTTONS_TIMELINE[name], "rerun")
            _need(len(reruns) == 1 and reruns[0]["states"] == expected[0]["states"],
                  f"stage {name} widget-state report differs from the measured wire")
            for kind in ("checkbox", "feedback", "button_group", "pagination", "menu_button", "link_button", "page_link", "download_button"):
                _need(len(_entries(timelines[name], kind)) == len(_entries(BUTTONS_TIMELINE[name], kind)),
                      f"stage {name} {kind} element list changed shape")
        menu_states = _entries(timelines["06-menu"], "rerun")[0]["states"]
        trigger = [state for state in menu_states if state.get("value_field") == "string_trigger_value"]
        _need(len(trigger) == 1 and trigger[0]["value"] == {"data": "CSV"},
              "the menu pick reports the one-shot string trigger of the selected option")
        mark("interaction_wires")

        for stage in stages:
            name = stage["name"]
            _need({key: (stage["dom"] or {}).get(key) for key in BUTTONS_DOMS[name]} == BUTTONS_DOMS[name],
                  f"stage {name} resolved DOM projection differs from the measured page")
        mark("dom_projection")

        for stage in stages:
            _need(not ((stage["dom"] or {}).get("exceptions") or []), f"stage {stage['name']} renders an exception")
        mark("no_exceptions")

        for stage in stages:
            finishes = [((frame.get("summary") or {}).get("script_finished") or {}).get("status")
                        for frame in stage["new_frames"]
                        if (frame.get("summary") or {}).get("type") == "script_finished"]
            _need(finishes == [0], f"stage {stage['name']} must finish exactly once FINISHED_SUCCESSFULLY")
        mark("finishes")

        root = pathlib.Path(observation.get("ipc_dir", ".")).resolve()
        for stage in stages:
            record = stage.get("screenshot") or {}
            _need(not pathlib.Path(record.get("file", "")).is_absolute(), "screenshot path must be relative")
            png = (root / record.get("file", "")).resolve()
            _need(png.is_relative_to(root) and png.is_file(), f"missing stage PNG {record.get('file')}")
            data = png.read_bytes()
            _need(data.startswith(b"\x89PNG\r\n\x1a\n") and hashlib.sha256(data).hexdigest() == record.get("sha256"),
                  f"stage PNG sha/magic mismatch for {record.get('file')}")
        mark("png_sources")
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError, StopIteration) as exc:
        for name in BUTTONS_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def buttons_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = buttons_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(BUTTONS_REQUIRED),
    }
