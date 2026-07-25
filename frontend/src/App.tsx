import { Routes, Route } from "react-router-dom";
import Layout from "./components/layout/Layout";
import ToolList from "./pages/ToolList";
import BlankToolPage from "./pages/tools/BlankToolPage";
import ChatToolPage from "./pages/tools/ChatToolPage";
import CodeAgentFlowVizPage from "./pages/tools/CodeAgentFlowVizPage";
import TaskDecomposerPage from "./pages/tools/TaskDecomposerPage";

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<ToolList />} />
        <Route path="/tools/blank_tool" element={<BlankToolPage />} />
        <Route path="/tools/chat_tool" element={<ChatToolPage />} />
        <Route path="/tools/code_agent_flow_viz" element={<CodeAgentFlowVizPage />} />
      </Route>
      <Route path="/tools/task_decomposer" element={<TaskDecomposerPage />} />
    </Routes>
  );
}

export default App;
