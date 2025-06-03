"""
Watches iMessage database file and logs to file when a deleted message has been detected
"""

import sys
from datetime import datetime
from pathlib import Path
from sqlite3 import connect
from time import sleep
from typing import Optional

import pandas as pd
from dotenv import dotenv_values
from pandera.pandas import DataFrameModel, Field
from pandera.typing import DataFrame, Series

import helper as hp


def eprint(msg):
    """Prints msg to stderr"""
    print(msg, file=sys.stderr)


ENV = dotenv_values()
TARGET_EMAIL_OR_PHONE_NUMBERS = ENV["TARGET_EMAIL_OR_PHONE_NUMERS"]
IMESSAGE_FILE = f"{Path.home()}/Library/Messages/chat.db"
LOGFILE = "LOGFILE"

if not TARGET_EMAIL_OR_PHONE_NUMBERS:
    eprint("Fill out your .env!")
    sys.exit(1)


class MessagesSchema(DataFrameModel):
    """Represents messages between you and a target person"""

    message_id: Series[int]
    is_from_me: Series[bool]
    text_combined: Series[str] = Field(nullable=True)
    text: Series[str] = Field(nullable=True)
    inferred_text: Series[str] = Field(nullable=True)
    timestamp: Series[pd.Timestamp]
    is_audio_message: bool
    message_effect: str
    reaction: str
    is_thread_reply: bool


def get_chat(
    target_email_or_phone_number: str,
    last_n: Optional[int] = None,
    filter_messages_from_me: bool = False,
) -> DataFrame[MessagesSchema]:
    """Gets chat between you and a target email/phone number

    Args:
        target_email_or_phone_number (str): Other persons email or phone number.
        * Phone number must be of format +12345678901
        last_n (Optional[int], optional): How many messages to retrieve organized from most recent.
        * None will return all messages.
        * Defaults to None.
        filter_messages_from_me (bool, optional): Filter out all messages from me.
        * Defaults to False.

    Returns:
        DataFrame[MessagesSchema]: Dataframe of messages in thread
    """
    conn = connect(IMESSAGE_FILE)

    with conn as cur:
        handle = cur.execute(
            "select * from handle WHERE id=? AND service=='iMessage'",
            (target_email_or_phone_number,),
        ).fetchone()
        if handle is None:
            print("Failed to fetch handle_id")
            sys.exit(1)
        handle_id = handle[0]

    limit = ""
    if last_n:
        limit = f"LIMIT {last_n}"
    filter_your_messages_query = ""
    if filter_messages_from_me:
        filter_your_messages_query = "AND is_from_me=0"
    messages = pd.read_sql_query(
        f"""select *,
        datetime(date/1000000000 + strftime("%s", "2001-01-01") ,"unixepoch","localtime") as date_utc 
        FROM message 
        WHERE handle_id=? 
        {filter_your_messages_query}
        ORDER BY date DESC {limit}""",
        conn,
        params=(handle_id,),
    )
    messages.rename(columns={"ROWID": "message_id"}, inplace=True)

    messages["inferred_text"] = messages["attributedBody"].apply(hp.clean_text)
    messages["text_combined"] = messages.apply(
        lambda row: row["inferred_text"] if pd.isnull(row["text"]) else row["text"],
        axis=1,
    )
    messages["message_effect"] = messages["expressive_send_style_id"].apply(
        hp.detect_message_effect
    )
    messages["is_thread_reply"] = (~messages["thread_originator_guid"].isnull()).astype(
        int
    )
    messages["reaction"] = messages["associated_message_type"].apply(hp.detect_reaction)
    messages["timestamp"] = messages["date_utc"].apply(pd.Timestamp)
    # removing '\r' from the text of the messages as they interfere with the to_csv command.
    messages["text"] = messages["text"].str.replace("\r", "")
    messages["text_combined"] = messages["text_combined"].str.replace("\r", "")
    messages["inferred_text"] = messages["inferred_text"].str.replace("\r", "")
    messages["is_from_me"] = messages["is_from_me"].apply(bool)
    messages["is_audio_message"] = messages["is_audio_message"].apply(bool)
    messages["is_thread_reply"] = messages["is_thread_reply"].apply(bool)

    columns = [
        "message_id",
        "is_from_me",
        "text_combined",
        "text",
        "inferred_text",
        "timestamp",
        "is_audio_message",
        "message_effect",
        "reaction",
        "is_thread_reply",
    ]
    return MessagesSchema.validate(messages[columns])


def log_messages(email_or_phone_number: str, messages: DataFrame[MessagesSchema]):
    """Logs messages to LOGFILE

    Args:
        email_or_phone_number (str): Email or phone number of target 
        messages (DataFrame[MessagesSchema]): Messages to be logged
    """
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"==={datetime.now()}===\n")
        for _, message in messages.iterrows():
            f.write(f">>> {email_or_phone_number} {message["timestamp"]}\n")
            f.write(f"\tText combined: {message["text_combined"]}\n")
            f.write(f"\tText: {message["text"]}\n")
            f.write(f"\tInferred Text: {message["inferred_text"]}\n")
            f.write(f"\tIs Audio Message: {message["is_audio_message"]}\n")
            f.write(f"\tMessage Effect: {message["message_effect"]}\n")
            f.write(f"\tReaction: {message["reaction"]}\n")
            f.write(f"\tIs Thread Reply: {message["is_thread_reply"]}\n")


if __name__ == "__main__":
    target_email_or_phone_numbers: list[str] = TARGET_EMAIL_OR_PHONE_NUMBERS.replace(" ", "").split(",")
    print("Watching...")
    last_messages: list[DataFrame[MessagesSchema]] = []
    for target_email_or_phone_number in target_email_or_phone_numbers:
        last_messages.append(get_chat(target_email_or_phone_number, 2, True))

    try:
        while True:
            new_messages_list = []
            for i, target_email_or_phone_number in enumerate(target_email_or_phone_numbers):
                new_messages = get_chat(target_email_or_phone_number, 2, True)
                new_messages_list.append(new_messages)
                if not last_messages[i].equals(new_messages):
                    log_messages(target_email_or_phone_number, last_messages[i])
                    print("Difference noticed...")
            else:
                sleep(0.5)
            last_messages = new_messages_list
    except KeyboardInterrupt:
        print("Exiting...")
