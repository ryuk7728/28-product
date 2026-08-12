import { useEffect, useRef, useState } from "react";
import { useRoomChat } from "../hooks/useRoomChat";

type Props = {
  roomCode: string;
  playerToken: string;
  localSeatIndex: number;
};

export function RoomChat({ roomCode, playerToken, localSeatIndex }: Props) {
  const { connected, messages, error, sendChat } = useRoomChat(roomCode, playerToken);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [lastReadCount, setLastReadCount] = useState(0);
  const listRef = useRef<HTMLDivElement | null>(null);
  const unread = open
    ? 0
    : messages
        .slice(lastReadCount)
        .filter((message) => message.seatIndex !== localSeatIndex).length;

  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => {
        if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
      });
    }
  }, [messages, open]);

  const submit = () => {
    if (sendChat(draft)) setDraft("");
  };

  return (
    <aside className={`room-chat ${open ? "open" : ""}`}>
      <button
        type="button"
        className="room-chat-toggle"
        onClick={() => {
          const nextOpen = !open;
          setOpen(nextOpen);
          setLastReadCount(messages.length);
        }}
        aria-expanded={open}
        aria-label={open ? "Close chat" : "Open chat"}
      >
        <span>Chat</span>
        {unread > 0 ? <b>{Math.min(unread, 9)}</b> : null}
      </button>

      {open ? (
        <div className="room-chat-panel">
          <header>
            <span>Room chat</span>
            <i className={connected ? "online" : ""} title={connected ? "Connected" : "Reconnecting"} />
          </header>
          <div className="room-chat-messages" ref={listRef} aria-live="polite">
            {messages.length === 0 ? (
              <p className="room-chat-empty">No messages yet.</p>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`room-chat-message ${message.seatIndex === localSeatIndex ? "mine" : ""}`}
                >
                  <div>
                    <strong>{message.senderName}</strong>
                    <time>
                      {new Date(message.sentAtEpochMs).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </time>
                  </div>
                  <p>{message.text}</p>
                </div>
              ))
            )}
          </div>
          {error ? <div className="room-chat-error">{error}</div> : null}
          <form
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              maxLength={280}
              placeholder={connected ? "Message your partner" : "Reconnecting..."}
              disabled={!connected}
              aria-label="Chat message"
            />
            <button type="submit" disabled={!connected || !draft.trim()} aria-label="Send chat">
              Send
            </button>
          </form>
        </div>
      ) : null}
    </aside>
  );
}
