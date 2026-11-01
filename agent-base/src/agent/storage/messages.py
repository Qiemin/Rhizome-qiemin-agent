"""PostgreSQL message serialization, saving and loading."""

import psycopg
from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict
from psycopg.types.json import Jsonb

from .sessions import SessionNotFoundError


def save_messages(
    database_url: str,
    session_id: str,
    messages: list[BaseMessage],
) -> None:
    if not session_id.strip():
        raise ValueError("会话标识不能为空")

    rows = [
        (session_id, position, Jsonb(message_to_dict(message)))
        for position, message in enumerate(messages)
    ]

    with psycopg.connect(database_url, connect_timeout=10) as connection:
        first_question = next(
            (message.text for message in messages if message.type == "human"), "新会话",
        )
        suggested_title = " ".join(first_question.split())[:40] or "新会话"
        session = connection.execute(
            """
            UPDATE sessions
            SET updated_at = clock_timestamp(),
                title = CASE WHEN title = '新会话' THEN %s ELSE title END
            WHERE session_id = %s RETURNING session_id
            """,
            (suggested_title, session_id),
        ).fetchone()
        if session is None:
            raise SessionNotFoundError(session_id)
        connection.execute(
            "delete from messages where session_id = %s",
            (session_id,),
        )
        if rows:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    insert into messages(
                        session_id, position, message_json
                    )
                    values(%s, %s, %s)
                    """,
                    rows,
                )


def load_messages(
    database_url: str,
    session_id: str,
) -> list[BaseMessage]:
    if not session_id.strip():
        raise ValueError("会话标识不能为空")

    with (
        psycopg.connect(database_url, connect_timeout=10) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            """
                select message_json
                from messages
                where session_id = %s
                order by position ASC
                """,
            (session_id,),
        )
        rows = cursor.fetchall()

    message_dicts = []
    for row in rows:
        message_dicts.append(row[0])

    return messages_from_dict(message_dicts)
