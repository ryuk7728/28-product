import { useEffect, useState } from "react";
import { GamePage } from "./pages/GamePage";
import {
  MultiplayerLobbyPage,
  type MultiplayerSession,
} from "./pages/MultiplayerLobbyPage";

const ACTIVE_SESSION_KEY = "28_product_active_session";

function isPhoneDevice() {
  const nav = navigator as Navigator & {
    userAgentData?: { mobile?: boolean };
  };
  if (nav.userAgentData?.mobile === true) return true;

  const phoneUserAgent =
    /Mobi|iPhone|iPod|Windows Phone|IEMobile|Opera Mini|BlackBerry/i.test(
      navigator.userAgent
    );
  const phoneSizedTouchScreen =
    window.matchMedia("(pointer: coarse)").matches &&
    Math.min(window.screen.width, window.screen.height) < 600;
  return phoneUserAgent || phoneSizedTouchScreen;
}

function loadSession(): MultiplayerSession | null {
  try {
    const raw = localStorage.getItem(ACTIVE_SESSION_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as MultiplayerSession;
    if (
      value?.roomCode &&
      value?.playerToken &&
      typeof value.seatIndex === "number"
    ) {
      return value;
    }
  } catch {
    localStorage.removeItem(ACTIVE_SESSION_KEY);
  }
  return null;
}

export default function App() {
  const [session, setSession] = useState<MultiplayerSession | null>(loadSession);
  const [phoneBlocked, setPhoneBlocked] = useState(isPhoneDevice);

  useEffect(() => {
    const refreshDeviceClass = () => setPhoneBlocked(isPhoneDevice());
    window.addEventListener("orientationchange", refreshDeviceClass);
    window.addEventListener("resize", refreshDeviceClass);
    return () => {
      window.removeEventListener("orientationchange", refreshDeviceClass);
      window.removeEventListener("resize", refreshDeviceClass);
    };
  }, []);

  useEffect(() => {
    if (session) {
      localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(session));
    } else {
      localStorage.removeItem(ACTIVE_SESSION_KEY);
    }
  }, [session]);

  const exitGame = () => {
    if (session?.roomCode) {
      localStorage.removeItem(`28_product_room_${session.roomCode.toUpperCase()}`);
    }
    setSession(null);
  };

  if (phoneBlocked) {
    return (
      <main className="phone-block-shell">
        <section className="phone-block-card" aria-labelledby="phone-block-title">
          <div className="product-brand compact"><span>28</span><b>Twenty-Eight</b></div>
          <div className="large-screen-mark" aria-hidden="true"><i /></div>
          <div className="eyebrow">A BIGGER TABLE AWAITS</div>
          <h1 id="phone-block-title">Play on a larger screen.</h1>
          <p>
            Twenty-Eight is currently available on desktops, laptops and tablets.
            Open this page there to take your seat.
          </p>
        </section>
      </main>
    );
  }

  if (!session) {
    return <MultiplayerLobbyPage onReady={setSession} />;
  }

  return (
    <GamePage
      gameId={session.gameId}
      roomCode={session.roomCode}
      playerToken={session.playerToken}
      playerSeatIndex={session.seatIndex}
      controlledSeatIndices={[session.seatIndex]}
      onGameEnd={exitGame}
      onExit={exitGame}
    />
  );
}
