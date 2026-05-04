import { Routes, Route } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import VideoPage from './pages/VideoPage'


function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/video" element={<VideoPage />} />
    </Routes>
  )
}

export default App