import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Predict from './pages/Predict'
import DataExplorer from './pages/DataExplorer'
import ModelPerformance from './pages/ModelPerformance'
import Insights from './pages/Insights'
import Planning from './pages/Planning'
import About from './pages/About'
import { Hero } from './components/ui'

const NotFound = () => <Hero eyebrow="404" title="Page not found">Use the menu to pick one of the available pages.</Hero>

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="predict" element={<Predict />} />
        <Route path="data-explorer" element={<DataExplorer />} />
        <Route path="model-performance" element={<ModelPerformance />} />
        <Route path="insights" element={<Insights />} />
        <Route path="planning" element={<Planning />} />
        <Route path="about" element={<About />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
