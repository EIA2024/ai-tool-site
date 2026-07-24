import { Routes, Route } from "react-router-dom";
import Layout from "./components/layout/Layout";
import ToolList from "./pages/ToolList";
import BlankToolPage from "./pages/tools/BlankToolPage";
import ChatToolPage from "./pages/tools/ChatToolPage";

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<ToolList />} />
        <Route path="/tools/blank_tool" element={<BlankToolPage />} />
        <Route path="/tools/chat_tool" element={<ChatToolPage />} />
      </Route>
    </Routes>
  );
}

export default App;
