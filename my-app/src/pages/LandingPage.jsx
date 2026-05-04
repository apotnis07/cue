import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"

const TYPE_COLORS = {
    ingredient: "#869489", // Primary sage green from your HTML
    measurement: "#C2B8A3",
    technique: "#A3B2C2",
    timing: "#C2A3A3",
}

export default function LandingPage() {
    const [url, setUrl] = useState("")
    const navigate = useNavigate()
    const [isBtnHovered, setIsBtnHovered] = useState(false);

    function extractVideoId(rawUrl) {
        try { return new URL(rawUrl).searchParams.get("v") }
        catch { return null }
    }

    function handleSubmit() {
        const vid = extractVideoId(url)
        if (!vid) return
        navigate(`/video?url=${encodeURIComponent(url)}`)
    }

    return (
        <div style={s.root}>
            {/* NAVIGATION */}
            <nav style={s.nav}>
                <div style={s.wordmark}>CUE</div>
                {/* <button style={s.navIconBtn}>
           <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>light_mode</span>
        </button> */}
            </nav>

            {/* HERO SECTION */}
            <motion.main
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                style={s.hero}
            >
                <div style={s.heroInner}>
                    <motion.section
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1, duration: 0.5 }}
                        style={s.heroText}
                    >
                        <h1 style={s.heroHeadline}>
                            EVERY STEP,<br />
                            <span style={s.heroAccent}>RIGHT ON CUE.</span>
                        </h1>
                        <p style={s.heroSub}>
                            Paste a cooking video. We'll index every ingredient, technique, and timing cue — so you never have to rewind again.
                        </p>
                    </motion.section>

                    {/* INPUT AREA */}
                    <motion.section
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2, duration: 0.5 }}
                        style={s.inputSection}
                    >
                        <label style={s.inputLabel}>YOUTUBE URL</label>
                        <div style={s.inputRow}>
                            <input
                                style={s.input}
                                type="text"
                                placeholder="https://www.youtube.com/watch?v=..."
                                value={url}
                                onChange={(e) => setUrl(e.target.value)}
                                onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                            />
                            <button
                                style={{
                                    ...s.submitBtn,
                                    // The specific glow effect from journal.html[cite: 3]
                                    // boxShadow: isBtnHovered
                                    //     ? "0 0 20px rgba(134, 148, 137, 0.4)" 
                                    //     : "0 10px 15px -3px rgba(0, 0, 0, 0.3)",
                                    filter: isBtnHovered ? "brightness(1.1)" : "brightness(1)"
                                }}
                                onMouseEnter={() => setIsBtnHovered(true)}
                                onMouseLeave={() => setIsBtnHovered(false)}
                                onClick={handleSubmit}
                            >
                                Analyze Video
                            </button>
                        </div>
                    </motion.section>
                </div>
            </motion.main>
        </div>
    )
}

const s = {
    root: {
        minHeight: "100vh",
        background: "#0a0a0a", // Exact background color[cite: 1]
        color: "#e6e1e0", // Exact on-surface color[cite: 1]
        fontFamily: "'Manrope', sans-serif",
        display: "flex",
        flexDirection: "column",
    },
    // Inside your s object in LandingPage.jsx
    nav: {
        position: "fixed",
        top: 0, left: 0, right: 0,
        zIndex: 50,
        height: "80px",
        background: "#0a0a0a", // Matches the root background
        borderBottom: "none",  // <--- CHANGE THIS FROM '1px solid...' TO 'none'[cite: 2]
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 32px",
    },
    wordmark: {
        fontSize: "20px",
        fontWeight: "900",
        letterSpacing: "0.05em",
        color: "#ffffff",
        // fontStyle: "italic",
    },
    navIconBtn: {
        background: "none",
        border: "none",
        color: "#8a938e",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
    },
    hero: {
        flex: 1,
        display: "flex",
        justifyContent: "center",
        paddingTop: "128px",
    },
    heroInner: {
        maxWidth: "900px",
        width: "100%",
        padding: "64px 32px",
        display: "flex",
        flexDirection: "column",
        gap: "48px",
    },
    heroText: {
        display: "flex",
        flexDirection: "column",
        gap: "16px",
    },
    heroHeadline: {
        fontSize: "clamp(40px, 6vw, 72px)", // Increased for editorial look[cite: 1]
        fontWeight: "800",
        lineHeight: "0.95",
        letterSpacing: "-0.05em",
        color: "#E6E1E0",
        margin: 0,
    },
    heroAccent: {
        fontWeight: "300",
        fontStyle: "italic",
        color: "#869489", // Primary sage green[cite: 1]
    },
    heroSub: {
        fontSize: "18px",
        lineHeight: "1.6",
        color: "#8A8E8C", // on-surface-variant[cite: 1]
        maxWidth: "520px",
        fontWeight: "400",
    },
    inputSection: {
        display: "flex",
        flexDirection: "column",
        gap: "0",
        background: "#1c1c1c", // Matches bg-surface-container-low
        borderRadius: "12px", // Matches rounded-xl
        padding: "32px", // Matches p-8[cite: 3]
        border: "1px solid rgba(65, 73, 69, 0.1)", // Matches border-outline-variant/10[cite: 3]
        transition: "all 0.5s duration",
    },
    inputLabel: {
        fontSize: "12px", // Matches text-xs[cite: 3]
        letterSpacing: "0.2em", // Matches tracking-widest[cite: 3]
        color: "rgba(134, 148, 137, 0.7)", // Matches text-primary/70[cite: 3]
        fontWeight: "800",
        textTransform: "uppercase",
        marginBottom: "16px",
    },
    inputRow: {
        display: "flex",
        flexDirection: "column", // Stacked to match the Journal flow[cite: 3]
        gap: "24px"
    },
    input: {
        width: "100%",
        background: "transparent",
        color: "#e6e1e0", // Matches text-on-surface[cite: 3]
        border: "none",
        padding: "0",
        fontSize: "18px", // Matches text-lg[cite: 3]
        fontFamily: "'Manrope', sans-serif",
        outline: "none",
        borderBottom: "1px solid rgba(138, 147, 142, 0.2)", // Subtle underline for the input area
    },
    submitBtn: {
        alignSelf: "flex-end",
        background: "linear-gradient(135deg, #869489 0%, #394b41 100%)", // Matches editorial-gradient
        color: "#0e1f17", // Matches text-on-primary
        border: "none",
        padding: "12px 32px",
        borderRadius: "9999px",
        fontSize: "14px",
        fontWeight: "800",
        cursor: "pointer",
        transition: "all 0.3s ease", // Smooth transition for the glow
        boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.3)", // Base shadow
    },
    bento: {
        display: "grid",
        gridTemplateColumns: "1.6fr 1fr", // Refined 8:4 ratio[cite: 1]
        gap: "24px",
    },
    bentoMain: {
        background: "#121212", // surface-container-low[cite: 1]
        border: "1px solid #2b2b2b",
        padding: "40px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        minHeight: "240px",
    },
    bentoOverlay: {
        display: "flex",
        flexDirection: "column",
        gap: "8px",
    },
    bentoLabel: {
        fontSize: "10px",
        letterSpacing: "0.4em",
        color: "#869489",
        fontWeight: "800",
    },
    bentoTitle: {
        fontSize: "24px",
        fontWeight: "800",
        letterSpacing: "-0.02em",
        color: "#ffffff",
        lineHeight: "1.1",
    },
    bentoGrid: {
        display: "flex",
        gap: "12px",
        flexWrap: "wrap",
        marginTop: "24px",
    },
    bentoTag: {
        fontSize: "10px",
        letterSpacing: "0.1em",
        fontWeight: "800",
        padding: "8px 16px",
        background: "#1c1c1c",
        border: "1px solid #2b2b2b",
        color: "#869489",
    },
    bentoSide: {
        background: "#1c1c1c", // surface-container[cite: 1]
        border: "1px solid #2b2b2b",
        padding: "32px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
    },
    bentoSideTop: {
        display: "flex",
        flexDirection: "column",
        gap: "16px",
    },
    bentoSideIcon: {
        fontSize: "32px",
        color: "#869489",
    },
    bentoSideText: {
        fontSize: "14px",
        color: "#e6e1e0",
        lineHeight: "1.5",
        fontWeight: "400",
    },
    progressTrackBento: {
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        marginTop: "20px"
    },
    progressStep: {
        display: "flex",
        alignItems: "center",
        gap: "12px",
    },
    progressDotBento: {
        width: "6px",
        height: "6px",
        borderRadius: "50%",
    },
    progressStepLabel: {
        fontSize: "9px",
        letterSpacing: "0.15em",
        fontWeight: "800",
    },
}