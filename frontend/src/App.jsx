import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import PortfolioOverview from "./pages/PortfolioOverview";
import HealthCard from "./pages/HealthCard";
import Simulator from "./pages/Simulator";
import Compare from "./pages/Compare";
import Analytics from "./pages/Analytics";

function App() {
  return (
    <BrowserRouter basename='/ps3'>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<PortfolioOverview />} />
          <Route path="/health-card/:id" element={<HealthCard />} />
          <Route path="/simulate" element={<Simulator />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/analytics" element={<Analytics />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;

