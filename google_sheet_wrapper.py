"""Production storage backend: a Google Sheet the performers read live."""

import logging

from googleapiclient.discovery import build
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class GoogleSheetWrapper:
    """Reads and writes a single user's row in a Google Sheet.

    Implements the same two-method interface as ``storage.InMemoryStore``
    (``get_user_responses`` / ``update_user_responses``).
    """

    def __init__(self, spreadsheet_id, service_account_file, scope):
        self.spreadsheet_id = spreadsheet_id
        self.service_account_file = service_account_file
        self.scope = scope
        self.service = self.initialize_service()
        self.sheet_name = "Users"

    def initialize_service(self):
        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_file, scopes=[self.scope]
        )
        return build("sheets", "v4", credentials=credentials)

    def get_user_responses(self, user_id):
        """Return the first row matching ``user_id``, or None if not found."""
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=self.sheet_name)
            .execute()
        )
        for row in result.get("values", []):
            if row and row[0] == user_id:
                return row
        return None

    def update_user_responses(self, user_id, updates):
        """Write ``{column_index: value}`` updates to the user's row.

        :raises ValueError: if the user_id is not present in the sheet.
        """
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=self.sheet_name)
            .execute()
        )
        values = result.get("values", [])

        row_index = None
        for i, row in enumerate(values):
            if row and row[0] == user_id:
                row_index = i + 1
                break
        if row_index is None:
            raise ValueError("User ID not found.")

        requests = [
            {
                "updateCells": {
                    "rows": {"values": [{"userEnteredValue": {"stringValue": value}}]},
                    "fields": "userEnteredValue",
                    "start": {
                        "sheetId": 0,
                        "rowIndex": row_index - 1,
                        "columnIndex": column,
                    },
                }
            }
            for column, value in updates.items()
        ]

        logger.debug("Writing %d cell update(s) for user %s", len(requests), user_id)
        return (
            self.service.spreadsheets()
            .batchUpdate(spreadsheetId=self.spreadsheet_id, body={"requests": requests})
            .execute()
        )
