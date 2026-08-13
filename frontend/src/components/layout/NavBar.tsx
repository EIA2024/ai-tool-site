import { Link } from "react-router-dom";

/** Site chrome: brand + the operator-facing Usage link. The Dock (home) is the
 * tool navigation surface, so no tool links are hardcoded here. */
export default function NavBar() {
  return (
    <nav className="navbar">
      <Link to="/" className="nav-brand">
        AI Tool Site
      </Link>
      <div className="nav-links">
        <Link to="/usage">Usage</Link>
      </div>
    </nav>
  );
}
