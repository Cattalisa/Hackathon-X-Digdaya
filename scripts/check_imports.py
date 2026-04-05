modules = [
    'backend.services.news_service',
    'backend.services.data_service',
    'backend.agents.sentiment_agent'
]

import importlib
for m in modules:
    try:
        importlib.import_module(m)
        print(m + ' -> OK')
    except Exception as e:
        print(m + ' -> ERROR: ' + str(e))
