import json
import re


class TopologyVisualizer:
    """A dedicated builder for generating interactive HTML dashboards from a DRS Network."""

    def __init__(self, network):
        self.network = network
        self._snapshots = {}

    # TODO: this is mining specific and gross
    def _format_name(self, name: str) -> str:
        if name == "Source":
            return "Mine Extraction"
        if name == "Sink":
            return "Processing Plant"
        name = name.replace("True", "").replace("Belief", "")
        name = re.sub(r"([a-z])([A-Z0-9])", r"\1 \2", name)
        return name.replace("Stock", "Stockpile").strip()

    def capture_mode_state(self, mode_name: str):
        """Extracts the mathematical state of the network for the current mode."""
        snapshot = {"nodes": [], "edges": []}

        # Gather Node Data
        for node in self.network.nodes:
            node_attrs_html = []
            mass_level = node.accumulations.get("mass")

            for attr, level in node.accumulations.items():
                if attr == "mass":
                    val_str, rate_str = (
                        f"{level.value:,.1f} t",
                        f"{level.rate:,.1f} t/d",
                    )
                else:
                    intensive_val = (
                        (level.value / mass_level.value)
                        if (mass_level and mass_level.value > 0)
                        else 0.0
                    )
                    val_str = (
                        f"{intensive_val:,.2f}%"
                        if "grade" in attr.lower()
                        else f"{intensive_val:,.2f}"
                    )
                    rate_str = "N/A (Intensive)"

                low = level.lower_threshold if level.lower_threshold > -1e5 else "-∞"
                high = level.upper_threshold if level.upper_threshold < 1e5 else "∞"
                rate_color = (
                    "red"
                    if level.rate < 0
                    else ("green" if level.rate > 0 else "black")
                )

                row = (
                    f"<tr><td style='padding-right:10px;'><b>{attr.upper()}</b></td><td>{val_str}</td></tr>"
                    f"<tr><td></td><td style='color:{rate_color}; font-size:11px;'>Δ {rate_str}</td></tr>"
                    f"<tr><td></td><td style='color:gray; font-size:11px;'>Limits: [{low}, {high}]</td></tr>"
                )
                node_attrs_html.append(row)

            display_name = self._format_name(node.name)
            tooltip = f"<div style='font-family:sans-serif; min-width:180px;'><h4 style='margin:0 0 5px 0;'>{display_name}</h4><hr style='margin:5px 0;'><table style='font-size:12px; margin-bottom:5px;'>{''.join(node_attrs_html)}</table></div>"

            inflow = sum(e.flow_rates.get("mass", 0.0) for e in node.in_edges)
            outflow = sum(e.flow_rates.get("mass", 0.0) for e in node.out_edges)

            if inflow > 0 and outflow > 0:
                rate_label = (
                    f"\nFlow: {inflow:,.0f}/d"
                    if abs(inflow - outflow) < 1e-3
                    else f"\nIn: {inflow:,.0f} | Out: {outflow:,.0f}"
                )
            elif inflow > 0:
                rate_label = f"\nIn: {inflow:,.0f}/d"
            elif outflow > 0:
                rate_label = f"\nOut: {outflow:,.0f}/d"
            else:
                rate_label = "\nIdle"

            snapshot["nodes"].append(
                {
                    "id": node.name,
                    "title": tooltip,
                    "label": f"{display_name}{rate_label}",
                }
            )

        # Gather Edge Data
        for edge in self.network.edges:
            mass_flow = edge.flow_rates.get("mass", 0.0)
            flows = [f"Mass: {mass_flow:,.0f} t/d"] if mass_flow > 0 else []

            for k, v in edge.flow_rates.items():
                if k == "mass" or v <= 0:
                    continue
                if mass_flow > 0:
                    intensive = v / mass_flow
                    flows.append(
                        f"Grade: {intensive:,.2f}%"
                        if "grade" in k.lower()
                        else f"{k.capitalize()}: {intensive:,.2f}"
                    )
                else:
                    flows.append(f"{k.capitalize()}: {v:,.1f}")

            flow_text = "\n".join(flows) if flows else "Idle"

            snapshot["edges"].append(
                {
                    "id": edge.name,
                    "title": f"<b>{self._format_name(edge.name)}</b><br>{flow_text.replace('\n', '<br>')}",
                    "label": flow_text,
                    "width": 3 if mass_flow > 0 else 1,
                    "color": "#666666" if mass_flow > 0 else "#D3D3D3",
                }
            )

        self._snapshots[mode_name] = snapshot

    def build(self, filename="interactive_topology.html"):
        """Compiles the captured snapshots into a standalone interactive HTML file."""
        import networkx as nx
        from pyvis.network import Network as PyvisNetwork

        if not self._snapshots:
            raise ValueError("No states captured! Call capture_mode_state() first.")

        G = nx.DiGraph()
        for edge in self.network.edges:
            u, v = (edge.source.name if edge.source else "Source"), (
                edge.target.name if edge.target else "Sink"
            )
            if u not in G:
                G.add_node(
                    u,
                    label=self._format_name(u),
                    color="#ADD8E6" if "Stock" in u else "#90EE90",
                    shape="box",
                )
            if v not in G:
                G.add_node(
                    v,
                    label=self._format_name(v),
                    color="#FFB6C1" if "Mill" in v or v == "Sink" else "#ADD8E6",
                    shape="box",
                )
            G.add_edge(
                u, v, id=edge.name, arrows="to", font={"size": 10, "align": "middle"}
            )

        net = PyvisNetwork(directed=True, height="800px", width="100%")
        net.from_nx(G)
        net.set_options(
            """{"physics": {"barnesHut": {"gravitationalConstant": -30000, "centralGravity": 0.3, "springLength": 100, "springConstant": 0.04, "damping": 0.09, "avoidOverlap": 1}, "minVelocity": 0.75}}"""
        )
        net.write_html(filename)

        # Inject the UI logic using a clean template
        self._inject_ui(filename)
        print(f"Success! Dashboard built: {filename}")

    def _inject_ui(self, filename):
        """Privately handles the HTML file modification."""
        options_html = "".join(
            [f"<option value='{m}'>{m}</option>" for m in self._snapshots.keys()]
        )

        injection_template = f"""
        <div style="position: absolute; top: 20px; left: 20px; z-index: 9999; background: rgba(255,255,255,0.9); padding: 15px; border-radius: 8px; box-shadow: 0px 4px 6px rgba(0,0,0,0.1); font-family: sans-serif;">
            <h3 style="margin-top: 0; font-size: 16px;">System State</h3>
            <select id="modeDropdown" onchange="changeMode()" style="font-size: 14px; padding: 5px; width: 100%;">
                {options_html}
            </select>
        </div>
        <script>
            var snapshots = {json.dumps(self._snapshots)};
            function changeMode() {{
                var mode = document.getElementById("modeDropdown").value;
                var data = JSON.parse(JSON.stringify(snapshots[mode]));
                
                data.nodes.forEach(n => {{ if (typeof n.title === 'string') {{ let el = document.createElement('div'); el.innerHTML = n.title; n.title = el; }} }});
                data.edges.forEach(e => {{ if (typeof e.title === 'string') {{ let el = document.createElement('div'); el.innerHTML = e.title; e.title = el; }} }});
                
                nodes.update(data.nodes);
                edges.update(data.edges);
            }}
            window.onload = function() {{ setTimeout(changeMode, 500); }};
        </script>
        """

        with open(filename, "r+", encoding="utf-8") as f:
            html = f.read()
            f.seek(0)
            f.write(html.replace("</body>", injection_template + "\n</body>"))
            f.truncate()
