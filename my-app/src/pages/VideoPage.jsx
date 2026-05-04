import { useState, useRef, useEffect } from "react"
import { useSearchParams, useNavigate } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"

const TYPE_COLORS = {
  ingredient: "#869489", // Synchronized with Landing Page[cite: 1]
  measurement: "#C2B8A3",
  technique: "#A3B2C2",
  timing: "#C2A3A3",
}

function parseTimestamp(display) {
  const [mins, secs] = display.split(":").map(Number)
  return mins * 60 + secs
}

function formatDuration(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, "0")}`
}

export default function VideoPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const url = searchParams.get("url")

  const [phase, setPhase] = useState("processing")
  const [status, setStatus] = useState("Initialising pipeline...")
  const [currentStep, setCurrentStep] = useState(null)
  const [moments, setMoments] = useState([])
  const [videoInfo, setVideoInfo] = useState(null)
  const [activeIndex, setActiveIndex] = useState(null)
  const [currentTime, setCurrentTime] = useState(0)
  const segmentsContainerRef = useRef(null)
  const transcriptContainerRef = useRef(null)
  const [isLooping, setIsLooping] = useState(false);

  // FIXED: Restored missing Refs
  const playerRef = useRef(null)
  const activeCardRef = useRef(null)
  const activeTranscriptRef = useRef(null)

  const STEPS = ["download", "extract_audio", "transcribe", "detect_moments", "end"]
  const stepIndex = STEPS.indexOf(currentStep)

  useEffect(() => {
    if (!window.YT) {
      const tag = document.createElement("script")
      tag.src = "https://www.youtube.com/iframe_api"
      document.body.appendChild(tag)
    }
  }, [])

  useEffect(() => {
    const interval = setInterval(() => {
      if (playerRef.current && playerRef.current.getCurrentTime) {
        setCurrentTime(playerRef.current.getCurrentTime());
      }
    }, 500)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (!url) return
    let videoId
    try { videoId = new URL(url).searchParams.get("v") }
    catch { return }
    if (!videoId) return

    const init = () => {
      playerRef.current = new window.YT.Player("yt-player", {
        videoId,
        playerVars: { autoplay: 1, rel: 0, modestbranding: 1 },
      })
    }
    if (window.YT && window.YT.Player) init()
    else window.onYouTubeIframeAPIReady = init
  }, [url])

  useEffect(() => {
    if (!url) return
    const evtSource = new EventSource(
      `http://localhost:8000/process?url=${encodeURIComponent(url)}`
    )
    evtSource.addEventListener("status", (e) => {
      const data = JSON.parse(e.data)
      setStatus(data.message)
      if (data.step) setCurrentStep(data.step)
    })
    evtSource.addEventListener("moment", (e) => {
      setMoments((prev) => [...prev, JSON.parse(e.data)])

    })
    evtSource.addEventListener("complete", (e) => {
      setVideoInfo(JSON.parse(e.data))
      setPhase("ready")
      evtSource.close()
    })
    evtSource.addEventListener("error", () => {
      setStatus("Something went wrong.")
      evtSource.close()
    })
    return () => evtSource.close()
  }, [url])

  // Auto-scroll logic
  useEffect(() => {
    if (activeCardRef.current && segmentsContainerRef.current) {
      const container = segmentsContainerRef.current
      const card = activeCardRef.current
      const containerRect = container.getBoundingClientRect()
      const cardRect = card.getBoundingClientRect()
      const offset = cardRect.top - containerRect.top + container.scrollTop - container.clientHeight / 2 + card.clientHeight / 2
      container.scrollTo({ top: offset, behavior: "smooth" })
    }

    if (activeTranscriptRef.current && transcriptContainerRef.current) {
      const container = transcriptContainerRef.current
      const line = activeTranscriptRef.current
      const containerRect = container.getBoundingClientRect()
      const lineRect = line.getBoundingClientRect()
      const offset = lineRect.top - containerRect.top + container.scrollTop - container.clientHeight / 2 + line.clientHeight / 2
      container.scrollTo({ top: offset, behavior: "smooth" })
    }
  }, [currentTime])

  function seekTo(timestamp_display) {
    const seconds = parseTimestamp(timestamp_display);
    if (playerRef.current?.seekTo) {
      playerRef.current.seekTo(seconds, true);
      // Crucial: ensure the video keeps playing after the jump
      if (playerRef.current.getPlayerState() !== 1) {
        playerRef.current.playVideo();
      }
    }
  }

  function handleTranscriptClick(timestamp_display) {
    seekTo(timestamp_display)
  }


  // const activeMoment = activeIndex !== null ? moments[activeIndex] : null

  // const activeMoment = moments.find((m, i) => {
  //   const next = moments[i + 1];
  //   return currentTime >= m.start && (!next || currentTime < next.start);
  // });

  const activeMoment = moments.find((m, i) => {
    const nextMoment = moments[i + 1];
    const startSec = m.start !== undefined ? Number(m.start) : parseTimestamp(m.timestamp_display);
    const nextStartSec = nextMoment
      ? (nextMoment.start !== undefined ? Number(nextMoment.start) : parseTimestamp(nextMoment.timestamp_display))
      : videoInfo?.duration || 999999;

    return currentTime >= startSec && currentTime < nextStartSec;
  });

  const handleNext = () => {
    const next = moments.find(m => {
      const s = m.start !== undefined ? Number(m.start) : parseTimestamp(m.timestamp_display);
      return s > currentTime + 0.5;
    });
    if (next) seekTo(next.timestamp_display);
  };

  const handleLast = () => {
    const prev = [...moments].reverse().find(m => {
      const s = m.start !== undefined ? Number(m.start) : parseTimestamp(m.timestamp_display);
      return s < currentTime - 2;
    });
    if (prev) seekTo(prev.timestamp_display);
  };

  // 4. Loop Engine
  useEffect(() => {
    if (isLooping && activeMoment && playerRef.current) {
      // 1. Get the index of what's playing now
      const currentIndex = moments.findIndex(m => m.timestamp_display === activeMoment.timestamp_display);

      // 2. Identify the "Tripwire" (the very next moment)
      const nextMoment = moments[currentIndex + 1];

      if (nextMoment) {
        const nextStart = nextMoment.start !== undefined ? nextMoment.start : parseTimestamp(nextMoment.timestamp_display);

        // 3. If we hit or pass the next moment's start, jump back
        // We use >= instead of == because the player might jump from 10.1 to 10.3 seconds
        if (currentTime >= nextStart - 0.2) {
          const currentStart = activeMoment.start !== undefined ? activeMoment.start : parseTimestamp(activeMoment.timestamp_display);
          playerRef.current.seekTo(currentStart, true);
        }
      } else if (videoInfo?.duration && currentTime >= videoInfo.duration - 0.5) {
        // 4. Special case: If it's the last moment, loop back when video ends
        const currentStart = activeMoment.start !== undefined ? activeMoment.start : parseTimestamp(activeMoment.timestamp_display);
        playerRef.current.seekTo(currentStart, true);
      }
    }
  }, [currentTime, isLooping, activeMoment, moments, videoInfo]);

  return (
    <div style={s.root}>
      {/* NAVIGATION */}
      <header style={s.header}>
        <div style={s.wordmark}>CUE</div>
        <div className="flex items-center gap-4">
          <button style={s.newVideoBtn} onClick={() => navigate("/")} className="active:scale-95">
            New Video
          </button>
        </div>
      </header>

      <main style={s.main}>
        {/* VIDEO SECTION */}
        <section style={s.videoSection}>
          <div style={s.videoAspect}>
            <div id="yt-player" style={s.player} />
          </div>
        </section>

        {/* TITLE + META */}
        <section style={s.metaSection}>
          <div style={s.metaLeft}>
            <h1 style={s.videoTitle}>
              {videoInfo?.title?.toUpperCase() || "PROCESSING VIDEO..."}
            </h1>
            <div style={s.metaRow}>
              {videoInfo && (
                <>
                  <div style={s.metaItem}>
                    <span style={s.metaLabel}>STEPS</span>
                    <span style={s.metaValue}>{videoInfo.total_moments}</span>
                  </div>
                  <div style={s.metaItem}>
                    <span style={s.metaLabel}>DURATION</span>
                    <span style={s.metaValue}>{formatDuration(videoInfo.duration)} MIN</span>
                  </div>
                  <div style={s.metaItem}>
                    <span style={s.metaLabel}>STATUS</span>
                    <span style={{ ...s.metaValue, color: "#869489" }}>INDEXED</span>
                  </div>
                </>
              )}
            </div>
          </div>
          <div style={s.metaRight}>
            {activeMoment ? (
              <motion.div
                key={activeMoment.timestamp_display}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                style={s.activeChip}
              >
                <span style={{ color: "#869489", fontSize: "10px", letterSpacing: "0.2em", fontWeight: "800" }}>
                  CURRENT CUE
                </span>
                <span style={s.activeChipTime}>{activeMoment.timestamp_display}</span>

                <div style={s.controlsRow}>
                  {/* LAST */}
                  <button onClick={handleLast} style={s.iconBtn} title="Last Moment">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M19 20L9 12l10-8v16zM5 19V5" />
                    </svg>
                  </button>

                  {/* LOOP */}
                  <button
                    onClick={() => setIsLooping(!isLooping)}
                    style={{ ...s.iconBtn, color: isLooping ? "#869489" : "#ffffff", borderColor: isLooping ? "#869489" : "#1c1c1c" }}
                    title="Loop Current"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M17 2l4 4-4 4" /><path d="M3 11v-1a4 4 0 014-4h14" /><path d="M7 22l-4-4 4-4" /><path d="M21 13v1a4 4 0 01-4 4H3" />
                    </svg>
                  </button>

                  {/* NEXT */}
                  <button onClick={handleNext} style={s.iconBtn} title="Next Moment">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M5 4l10 8-10 8V4zM19 5v14" />
                    </svg>
                  </button>
                </div>
              </motion.div>
            ) : (
              <div style={{ ...s.activeChip, opacity: 0.3, justifyContent: 'center', alignItems: 'center' }}>
                <span style={s.metaLabel}>WAITING FOR CUE...</span>
              </div>
            )}
          </div>
        </section>

        {/* CONTENT GRID */}
        <div style={s.grid}>
          {/* SEGMENTS */}
          <section>
            <h2 style={s.sectionTitle}>
              <span style={{ fontStyle: 'italic', fontWeight: '300' }}>SEGMENTS</span>
              <span style={s.titleLine} />
            </h2>

            {phase === "processing" && (
              <div style={s.pipelineStatus}>
                <p style={s.statusMsg}>{status.toUpperCase()}</p>
                <div style={s.progressRow}>
                  {STEPS.slice(0, 4).map((step, i) => (
                    <div key={step} style={{
                      ...s.progressDot,
                      background: i <= stepIndex ? "#869489" : "#1c1c1c",
                      boxShadow: i === stepIndex ? "0 0 10px rgba(134, 148, 137, 0.5)" : "none"
                    }} />
                  ))}
                </div>
              </div>
            )}

            <div style={s.segmentsList} ref={segmentsContainerRef} className="custom-scrollbar">
              {moments.map((m, i) => {
                // const isActive = activeIndex === i;
                const nextMoment = moments[i + 1]
                const isActive = currentTime >= m.start && (!nextMoment || currentTime < nextMoment.start);
                // const isActive = currentTime >= m.start && currentTime < m.end
                return (
                  <div
                    key={i}
                    ref={isActive ? activeCardRef : null} // FIXED: Attached ref[cite: 5]
                    style={{ ...s.segmentCard, borderLeft: isActive ? "4px solid #869489" : "4px solid transparent" }}
                    onClick={() => seekTo(m.timestamp_display)}
                  >
                    <span style={s.segmentTime}>{m.timestamp_display}</span>
                    <p style={s.segmentText}>{m.text}</p>
                  </div>
                );
              })}
            </div>
          </section>

          {/* TRANSCRIPT */}
          <section>
            <h2 style={s.sectionTitle}>
              <span style={{ fontStyle: 'italic', fontWeight: '300' }}>TRANSCRIPT</span>
              <span style={s.titleLine} />
            </h2>
            <div style={s.transcriptBox} ref={transcriptContainerRef} className="custom-scrollbar">
              {videoInfo?.transcript?.map((line, i) => {
                // const isActive = activeIndex === i;
                const isActive = currentTime >= line.start && currentTime < line.end
                return (
                  <p
                    key={i}
                    ref={isActive ? activeTranscriptRef : null} // FIXED: Attached ref[cite: 5]
                    onClick={() => handleTranscriptClick(line.timestamp_display)}
                    style={{
                      ...s.transcriptLine,
                      color: isActive ? "#ffffff" : "#8A8E8C",
                      borderLeft: isActive ? "2px solid #869489" : "2px solid transparent"
                    }}>
                    <span style={s.transcriptTime}>{line.timestamp_display}</span>
                    {line.text}
                  </p>
                );
              })}
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}

const s = {
  root: {
    minHeight: "100vh",
    background: "#0a0a0a", // Matched Landing Page background[cite: 1]
    color: "#e6e1e0", // Matched Landing Page text color[cite: 1]
    fontFamily: "'Manrope', sans-serif",
  },
  header: {
    height: "80px",
    background: "#0a0a0a",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 32px",
    position: "fixed",
    top: 0, left: 0, right: 0,
    zIndex: 100,
  },
  wordmark: {
    fontSize: "20px",
    fontWeight: "900",
    color: "#ffffff",
    letterSpacing: "0.05em",
  },
  newVideoBtn: {
    // Layout & Position
    backgroundColor: "#869489", // bg-primary (Sage Green)
    color: "#0e1f17",           // text-on-primary
    padding: "8px 20px",        // px-6 py-2
    borderRadius: "8px",        // rounded-lg
    fontWeight: "700",          // font-bold
    fontSize: "14px",           // text-sm

    // Effects
    boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.3)", // shadow-lg
    transition: "transform 0.2s ease",                // transition-transform
    border: "none",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    // textTransform: "uppercase",
    // letterSpacing: "0.05em",
  },
  main: {
    paddingTop: "128px", // Matched hero spacing from Landing Page[cite: 3, 4]
    maxWidth: "1100px",
    margin: "0 auto",
    paddingLeft: "32px",
    paddingRight: "32px",
    paddingBottom: "100px",
  },
  videoAspect: {
    position: "relative",
    paddingTop: "56.25%",
    background: "#121212",
    borderRadius: "12px",
    overflow: "hidden",
    border: "1px solid #1c1c1c",
  },
  player: {
    position: "absolute",
    top: 0, left: 0, width: "100%", height: "100%",
  },
  metaSection: {
    marginTop: "40px",
    display: "grid",
    gridTemplateColumns: "1fr 300px",
    gap: "40px",
    borderBottom: "1px solid #1c1c1c",
    paddingBottom: "40px",
  },
  videoTitle: {
    fontSize: "32px",
    fontWeight: "800",
    letterSpacing: "-0.04em",
    lineHeight: "1.1",
    color: "#ffffff",
    marginBottom: "24px",
  },
  controlsRow: {
    display: "flex",
    justifyContent: "space-between",
    marginTop: "16px",
    paddingTop: "16px",
    borderTop: "1px solid #1c1c1c",
    gap: "8px"
  },
  iconBtn: {
    background: "#0a0a0a",
    border: "1px solid #1c1c1c",
    borderRadius: "6px",
    color: "#ffffff",
    padding: "10px",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "all 0.2s ease",
    flex: 1,
  },
  metaRow: {
    display: "flex",
    gap: "32px",
  },
  metaItem: { display: "flex", flexDirection: "column", gap: "4px" },
  metaLabel: { fontSize: "10px", letterSpacing: "0.2em", color: "#8A8E8C", fontWeight: "800" },
  metaValue: { fontSize: "14px", fontWeight: "600" },
  activeChip: {
    background: "#121212",
    padding: "24px",
    border: "1px solid #1c1c1c",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  activeChipTime: { fontSize: "32px", fontWeight: "300", fontStyle: "italic", color: "#ffffff" },
  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1.2fr",
    gap: "64px",
    marginTop: "48px",
  },
  sectionTitle: {
    fontSize: "18px",
    display: "flex",
    alignItems: "center",
    gap: "16px",
    marginBottom: "32px",
    color: "#869489",
  },
  titleLine: { height: "1px", background: "#1c1c1c", flex: 1 },
  segmentsList: {
    maxHeight: "500px",
    overflowY: "auto",
  },
  segmentCard: {
    padding: "16px 24px",
    background: "#121212",
    marginBottom: "8px",
    cursor: "pointer",
    transition: "all 0.2s ease",
  },
  segmentTime: { color: "#869489", fontSize: "12px", fontWeight: "800", marginBottom: "4px", display: "block" },
  segmentText: { fontSize: "14px", lineHeight: "1.5" },
  transcriptBox: {
    background: "#050505",
    padding: "32px",
    border: "1px solid #1c1c1c",
    height: "500px",
    overflowY: "auto",
  },
  transcriptLine: {
    fontSize: "15px",
    lineHeight: "1.8",
    marginBottom: "20px",
    paddingLeft: "16px",
    cursor: "pointer",
  },
  transcriptTime: { fontWeight: "800", color: "#869489", marginRight: "12px", fontSize: "12px" },
  pipelineStatus: { marginBottom: "32px" },
  statusMsg: { fontSize: "11px", letterSpacing: "0.1em", color: "#8A8E8C", marginBottom: "12px" },
  progressRow: { display: "flex", gap: "8px" },
  progressDot: { width: "40px", height: "4px", borderRadius: "2px" }
};