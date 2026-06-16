"""Per-user questionnaire state, persisted through a pluggable store."""

import logging
import os
from datetime import datetime

from storage import (
    COL_ALL_CONVO,
    COL_COMPLETION_TIME,
    COL_CURRENT_CONVO,
    COL_FULL_NAME,
    COL_HISTORY_NOTES,
    COL_PROGRESS,
    COL_START_TIME,
)

logger = logging.getLogger(__name__)

SCOPES = "https://www.googleapis.com/auth/spreadsheets"


def _default_store():
    """Build the production Google Sheets store from the environment.

    Imported lazily so local runs (which inject their own store) don't need
    the Google client libraries or any credentials.
    """
    from google_sheet_wrapper import GoogleSheetWrapper

    spreadsheet_id = os.environ["INTERMISSION_SHEET_ID"]
    service_account_file = os.environ.get(
        "GOOGLE_SERVICE_ACCOUNT_FILE", "keys/service_account.json"
    )
    return GoogleSheetWrapper(spreadsheet_id, service_account_file, SCOPES)


class User:
    def __init__(self, user_id, store=None):
        """
        :param user_id: Unique id which must appear in the store.
        :param store: Storage backend; defaults to Google Sheets from env.
        :raises ValueError: ("User not found") if user_id is not in the store.
        """
        self.store = store or _default_store()
        self.user_id = user_id

        row = self.store.get_user_responses(user_id)
        if row is None:
            raise ValueError("User not found")

        self.answers = {index: item for index, item in enumerate(row)} or {}
        self.dirty_idxs = set()

        logger.debug("Loaded user %s: %s", user_id, row)
        if self.get_current_progress() == 0:
            self.set_start_time()
            self.save()

    def save(self):
        if not self.dirty_idxs:
            return
        updates = {idx: self.answers[idx] for idx in self.dirty_idxs}
        self.store.update_user_responses(self.user_id, updates)
        self.dirty_idxs.clear()

    def set(self, idx: int, value: str):
        self.answers[idx] = value
        self.dirty_idxs.add(idx)

    def get(self, idx: int):
        return self.answers[idx]

    def append_answer(self, idx: int, value: str):
        if idx not in self.answers:
            self.set(idx, value)
        else:
            if self.answers[idx] != "":
                value = "\n" + value
            self.set(idx, self.answers[idx] + f"{value}")

    def get_current_progress(self) -> int:
        return int(self.answers.get(COL_PROGRESS, 0))

    def set_progress(self, value: int):
        self.set(COL_PROGRESS, str(value))

    def set_current_answer(self, value: str):
        idx = self.get_current_progress()
        self.append_answer(idx, value)

    # SPECIFIC COLUMNS
    def set_start_time(self):
        formatted_time = datetime.now().strftime("%H:%M:%S %a %d %b %Y")
        self.set(COL_START_TIME, formatted_time)
        self.set_progress(COL_FULL_NAME)

    def set_end_time(self):
        formatted_time = datetime.now().strftime("%H:%M:%S %a %d %b %Y")
        self.set(COL_COMPLETION_TIME, formatted_time)
        self.set_progress(COL_COMPLETION_TIME)

    def add_history(self, value: str):
        self.append_answer(COL_HISTORY_NOTES, value)

    def get_history(self):
        return self.answers.get(COL_HISTORY_NOTES, "")

    def add_to_current_convo(self, text: str, is_user: bool):
        name = "User" if is_user else "Amy"
        value = f"{name}: {text}"
        self.append_answer(COL_CURRENT_CONVO, value)
        self.append_answer(COL_ALL_CONVO, value)  # also add automatically to all

    def get_current_convo(self):
        return self.answers.get(COL_CURRENT_CONVO, "")

    def clear_current_convo(self):
        if COL_CURRENT_CONVO in self.answers:
            del self.answers[COL_CURRENT_CONVO]
