"""Storage backends for user questionnaire data.

The agent keeps each guest's answers in a row of cells, addressed by the
column indices below. ``User`` talks to a store through a tiny two-method
interface (``get_user_responses`` / ``update_user_responses``), so the same
conversation logic runs against Google Sheets in production or an in-memory
store locally — no AWS or Google credentials needed to demo it.
"""

# Column schema — the position of each field in a user's row.
COL_PROGRESS = 1
COL_START_TIME = 2
COL_HISTORY_NOTES = 3
COL_CURRENT_CONVO = 4
COL_ALL_CONVO = 5
COL_INTERNAL_NOTES = 6
COL_FULL_NAME = 11
COL_COMPLETION_TIME = 36  # must be last


class InMemoryStore:
    """A store that keeps everything in a dict — for local runs and tests.

    Unlike the Google Sheets store, an unknown user is auto-created rather
    than rejected, so ``cli.py`` can start a fresh conversation instantly.
    """

    def __init__(self):
        self._rows = {}  # user_id -> {column_index: value}

    def get_user_responses(self, user_id):
        cells = self._rows.setdefault(user_id, {0: user_id})
        width = max(cells) + 1
        return [cells.get(i, "") for i in range(width)]

    def update_user_responses(self, user_id, updates):
        cells = self._rows.setdefault(user_id, {0: user_id})
        for column, value in updates.items():
            cells[column] = value
