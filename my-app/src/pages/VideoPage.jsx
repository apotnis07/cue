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
    activeCardRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
    activeTranscriptRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
  }, [activeIndex])

  function seekTo(timestamp_display) {
    const seconds = parseTimestamp(timestamp_display)
    if (playerRef.current?.seekTo) {
      playerRef.current.seekTo(seconds, true)
      playerRef.current.playVideo()
    }
  }

  function goToMoment(index) {
    if (index < 0 || index >= moments.length) return
    setActiveIndex(index)
    seekTo(moments[index].timestamp_display)
  }

  const activeMoment = activeIndex !== null ? moments[activeIndex] : null

  return (
    <div style={s.root}>
      {/* NAVIGATION */}
      <header style={s.header}>
        <div style={s.wordmark}>CUE</div>
        <div className="flex items-center gap-4">
          <button style={s.newVideoBtn} onClick={() => navigate("/")}>
            ← NEW VIDEO
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
             {activeMoment && (
              <motion.div key={activeIndex} initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={s.activeChip}>
                <span style={{ color: "#869489", fontSize: "10px", letterSpacing: "0.2em", fontWeight: "800" }}>CURRENT CUE</span>
                <span style={s.activeChipTime}>{activeMoment.timestamp_display}</span>
              </motion.div>
            )}
          </div>
        </section>

        {/* CONTENT GRID */}
        <div style={s.grid}>
          {/* SEGMENTS */}
          <section>
            <h2 style={s.sectionTitle}>
              <span style={{fontStyle: 'italic', fontWeight: '300'}}>SEGMENTS</span>
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

            <div style={s.segmentsList} className="custom-scrollbar">
              {moments.map((m, i) => {
                const isActive = activeIndex === i;
                return (
                  <div 
                    key={i} 
                    ref={isActive ? activeCardRef : null} // FIXED: Attached ref[cite: 5]
                    style={{...s.segmentCard, borderLeft: isActive ? "4px solid #869489" : "4px solid transparent"}}
                    onClick={() => goToMoment(i)}
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
              <span style={{fontStyle: 'italic', fontWeight: '300'}}>TRANSCRIPT</span>
              <span style={s.titleLine} />
            </h2>
            <div style={s.transcriptBox} className="custom-scrollbar">
                {moments.map((m, i) => {
                    const isActive = activeIndex === i;
                    return (
                        <p 
                          key={i} 
                          ref={isActive ? activeTranscriptRef : null} // FIXED: Attached ref[cite: 5]
                          onClick={() => goToMoment(i)} 
                          style={{
                            ...s.transcriptLine,
                            color: isActive ? "#ffffff" : "#8A8E8C",
                            borderLeft: isActive ? "2px solid #869489" : "2px solid transparent"
                        }}>
                            <span style={s.transcriptTime}>{m.timestamp_display}</span>
                            {m.text}
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
    background: "transparent",
    border: "1px solid #2b2b2b",
    color: "#869489", // Sage green[cite: 1]
    padding: "8px 16px",
    fontSize: "11px",
    fontWeight: "800",
    cursor: "pointer",
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