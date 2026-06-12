import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx


def _infer_type(module) -> str:
    name = type(module).__name__.lower()
    if "mineface" in name or "mine" in name:
        return "mine"
    if "fleet" in name:
        return "fleet"
    if "plant" in name:
        return "plant"
    if "stockpile" in name:
        return "stockpile"
    if "controller" in name:
        return "controller"
    if "sensor" in name or "network" in name:
        return "sensor"
    if "generator" in name or "source" in name or "loader" in name or "data" in name:
        return "generator"
    if "model" in name:
        return "model"
    return "other"


_TYPE_COLORS = {
    "mine": "#D4A574",
    "fleet": "#5B9BD5",
    "plant": "#70AD47",
    "stockpile": "#ED7D31",
    "controller": "#FF6B6B",
    "sensor": "#9B59B6",
    "generator": "#00BCD4",
    "model": "#555555",
    "other": "#BDC3C7",
}

_TYPE_ORDER = ["model", "generator", "mine", "fleet", "plant", "stockpile", "controller", "sensor", "other"]


def plot_module_graph(model, show_vars=False, figsize=(14, 10), save_path=None):
    G = nx.DiGraph()
    module_paths = {}
    parent_of = {}

    for path, mod in model.named_modules():
        node_id = path if path else type(mod).__name__
        module_paths[node_id] = (path, mod)
        G.add_node(node_id, module=mod, path=path)

        if path:
            parts = path.rsplit(".", 1)
            parent_path = parts[0] if len(parts) > 1 else ""
            parent_of[node_id] = parent_path

    reader_node = {}
    for rpath, rmod in model.named_modules():
        for src_mod, dep_var in rmod._dependencies:
            for spath, smod in model.named_modules():
                if smod is src_mod:
                    src_id = spath if spath else type(smod).__name__
                    rdr_id = rpath if rpath else type(rmod).__name__
                    if src_id != rdr_id and src_id in G and rdr_id in G:
                        G.add_edge(src_id, rdr_id, var_name=dep_var.name, edge_type="read")
                    break

    for rpath, rmod in model.named_modules():
        for src_mod in rmod._flow_dependencies:
            for spath, smod in model.named_modules():
                if smod is src_mod:
                    src_id = spath if spath else type(smod).__name__
                    rdr_id = rpath if rpath else type(rmod).__name__
                    if src_id != rdr_id and src_id in G and rdr_id in G:
                        G.add_edge(src_id, rdr_id, edge_type="flow")
                    break

    pos = _tree_layout(G, parent_of, module_paths)

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_title("DRS Module Graph", fontsize=16, fontweight="bold", pad=20)
    ax.set_facecolor("#FAFAFA")
    ax.margins(0.15)

    node_colors = []
    node_sizes = []
    labels = {}
    for node_id in G.nodes():
        mod = G.nodes[node_id].get("module")
        t = _infer_type(mod) if mod else "other"
        node_colors.append(_TYPE_COLORS.get(t, "#BDC3C7"))

        path = G.nodes[node_id].get("path", "")
        short_name = path.split(".")[-1] if path else type(mod).__name__
        label = short_name

        if show_vars and mod is not None:
            var_names = list(mod._variables.keys())[:3]
            if var_names:
                label += "\n" + "\n".join(var_names[:3])
                if len(mod._variables) > 3:
                    label += f"\n+{len(mod._variables) - 3} more"

        labels[node_id] = label

        var_count = len(mod._variables) if mod is not None else 0
        node_sizes.append(max(800, 600 + var_count * 40))

    dep_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "read"]
    flow_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "flow"]

    nx.draw_networkx_edges(
        G, pos, ax=ax,
        edgelist=dep_edges,
        edge_color="#E74C3C",
        style="dashed",
        width=1.5,
        alpha=0.6,
        arrows=True,
        arrowsize=15,
        connectionstyle="arc3,rad=0.15",
    )

    if flow_edges:
        nx.draw_networkx_edges(
            G, pos, ax=ax,
            edgelist=flow_edges,
            edge_color="#3498DB",
            style="solid",
            width=2.0,
            alpha=0.8,
            arrows=True,
            arrowsize=15,
            connectionstyle="arc3,rad=0.15",
        )

    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=node_colors,
        node_size=node_sizes,
        edgecolors="#333333",
        linewidths=1.5,
        alpha=0.9,
    )

    nx.draw_networkx_labels(
        G, pos, ax=ax,
        labels=labels,
        font_size=8,
        font_weight="bold",
    )

    legend_patches = []
    for t in _TYPE_ORDER:
        if t == "other" and not any(_infer_type(G.nodes[n].get("module")) == "other" for n in G.nodes()):
            continue
        color = _TYPE_COLORS[t]
        label = t.capitalize() if t != "other" else "Other"
        legend_patches.append(mpatches.Patch(color=color, label=label, alpha=0.9))

    if dep_edges:
        legend_patches.append(mpatches.Patch(
            color="#E74C3C", label="Dependency (read)", alpha=0.6
        ))
    if flow_edges:
        legend_patches.append(mpatches.Patch(
            color="#3498DB", label="Data flow (transient)", alpha=0.8
        ))

    ax.legend(handles=legend_patches, loc="upper left", fontsize=9, framealpha=0.9)

    ax.axis("off")
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved module graph to {save_path}")

    return fig


def _tree_layout(G, parent_of, module_paths):
    depths = {}
    for node_id in G.nodes():
        path = G.nodes[node_id].get("path", "")
        depths[node_id] = path.count(".") + 1 if path else 0

    children_of = {}
    for node_id, parent_id in parent_of.items():
        children_of.setdefault(parent_id, []).append(node_id)

    max_depth = max(depths.values()) if depths else 1
    depth_groups = {}
    for node_id, d in depths.items():
        depth_groups.setdefault(d, []).append(node_id)

    x_spacing = 3.0
    y_spacing = 1.0

    pos = {}
    for d in sorted(depth_groups.keys()):
        x = d * x_spacing
        nodes_at_depth = depth_groups[d]
        y_center = 0.0
        for i, node_id in enumerate(nodes_at_depth):
            y = y_center + (i - (len(nodes_at_depth) - 1) / 2) * y_spacing
            pos[node_id] = (x, y)

    for node_id in G.nodes():
        if node_id not in pos:
            pos[node_id] = (0, 0)

    return pos


def _node_id(path):
    return ("root" if not path else path.replace(".", "_"))


def _node_label(path, mod, show_type=True):
    short = path.split(".")[-1] if path else type(mod).__name__
    if show_type:
        return f"{short} ({_infer_type(mod)})"
    return short


def _generate_mermaid(model) -> str:
    lines = []
    lines.append("flowchart TD")

    module_index = {}
    for path, mod in model.named_modules():
        module_index[id(mod)] = (path, mod)

    tree = {}
    for path, mod in model.named_modules():
        mod_id = id(mod)
        if path:
            parts = path.rsplit(".", 1)
            parent_path = parts[0] if len(parts) > 1 else ""
            parent_id = id(dict(model.named_modules()).get(parent_path))
            tree.setdefault(parent_id, []).append(mod_id)
        else:
            tree.setdefault(0, []).append(mod_id)

    rendered_mods = set()

    def _render_children(parent_mod_id, depth=0):
        prefix = "    " * depth
        for child_id in tree.get(parent_mod_id, []):
            if child_id in rendered_mods:
                continue
            rendered_mods.add(child_id)
            path, mod = module_index[child_id]
            nid = _node_id(path)
            label = _node_label(path, mod)
            grandchild_ids = tree.get(child_id, [])

            if grandchild_ids:
                lines.append(f'{prefix}subgraph {nid}["{label}"]')
                _render_children(child_id, depth + 1)
                lines.append(f"{prefix}end")
            else:
                t = _infer_type(mod)
                lines.append(f'{prefix}{nid}(["{label}"]):::{t}')

    _render_children(0)

    seen_edges = set()
    for rpath, rmod in model.named_modules():
        for src_mod, dep_var in rmod._dependencies:
            src_info = module_index.get(id(src_mod))
            if src_info is None:
                continue
            spath, _ = src_info
            rdr_path = rpath if rpath else ""
            if not spath or not rdr_path:
                continue
            src_id = _node_id(spath)
            rdr_id = _node_id(rdr_path)
            if src_id == rdr_id or src_id == "root" or rdr_id == "root":
                continue
            edge_key = (src_id, rdr_id, dep_var.name)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                lines.append(f"    {src_id} -->|{dep_var.name}| {rdr_id}")

    for rpath, rmod in model.named_modules():
        for src_mod in rmod._flow_dependencies:
            src_info = module_index.get(id(src_mod))
            if src_info is None:
                continue
            spath, _ = src_info
            rdr_path = rpath if rpath else ""
            if not spath or not rdr_path:
                continue
            src_id = _node_id(spath)
            rdr_id = _node_id(rdr_path)
            if src_id == rdr_id or src_id == "root" or rdr_id == "root":
                continue
            edge_key = (src_id, rdr_id, "flow")
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                lines.append(f"    {src_id} ==>|flow| {rdr_id}")

    mods_by_type = {}
    for path, mod in model.named_modules():
        t = _infer_type(mod)
        mods_by_type.setdefault(t, []).append((path, mod))

    if "generator" in mods_by_type and "mine" in mods_by_type:
        g_path = mods_by_type["generator"][0][0]
        m_path = mods_by_type["mine"][0][0]
        g_id = _node_id(g_path)
        m_id = _node_id(m_path)
        lines.append(f"    {g_id} -.->|data| {m_id}")

    if "fleet" in mods_by_type:
        f_path = mods_by_type["fleet"][0][0]
        f_id = _node_id(f_path)
        for spath, _ in mods_by_type.get("stockpile", []):
            s_id = _node_id(spath)
            edge_key = (f_id, s_id, "routing")
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                lines.append(f"    {f_id} -.->|routing| {s_id}")

    for t in _TYPE_ORDER:
        if t in mods_by_type:
            c = _TYPE_COLORS.get(t, "#BDC3C7")
            lines.insert(1, f"    classDef {t} fill:{c},stroke:#333,color:#111")

    return "\n".join(lines)


def save_module_graph_report(model, path_prefix="module_graph", show_vars=True):
    png_path = f"{path_prefix}.png"
    md_path = f"{path_prefix}.md"

    fig = plot_module_graph(model, show_vars=show_vars, save_path=png_path)
    plt.close(fig)

    dep_lines = []
    flow_lines = []
    for rpath, rmod in model.named_modules():
        for src_mod, dep_var in rmod._dependencies:
            for spath, smod in model.named_modules():
                if smod is src_mod:
                    src_name = spath if spath else type(smod).__name__
                    rdr_name = rpath if rpath else type(rmod).__name__
                    if src_name != rdr_name:
                        dep_lines.append(f"  - `{src_name}` → `{rdr_name}` reads `{dep_var.name}`")
                    break
        for src_mod in rmod._flow_dependencies:
            for spath, smod in model.named_modules():
                if smod is src_mod:
                    src_name = spath if spath else type(smod).__name__
                    rdr_name = rpath if rpath else type(rmod).__name__
                    if src_name != rdr_name:
                        flow_lines.append(f"  - `{src_name}` → `{rdr_name}` flow")
                    break

    module_list = []
    for path, mod in model.named_modules():
        short = path.split(".")[-1] if path else type(mod).__name__
        t = _infer_type(mod)
        v = list(mod._variables.keys())[:5]
        v_str = ", ".join(v) if v else "—"
        if len(mod._variables) > 5:
            v_str += f", +{len(mod._variables) - 5} more"
        module_list.append(f"| `{short}` | `{path if path else '(root)'}` | {t} | `{v_str}` |")

    mermaid_code = _generate_mermaid(model)

    deps_section = ""
    if dep_lines:
        deps_section = f"""## Data Dependencies (persistent variable reads)

The following read-dependencies were recorded during the simulation. An arrow `A → B` means module B reads a variable owned by module A.

{chr(10).join(dep_lines)}

"""
    if flow_lines:
        deps_section += f"""## Data Flow (transient)

The following transient flow-edges were recorded during the simulation. An arrow `A → B` means module A returned a `drs.Flow` value that was passed as input to module B.

{chr(10).join(flow_lines)}

"""

    md_content = f"""# DRS Module Graph — {type(model).__name__}

> Generated automatically by `drs.vis.module_graph.save_module_graph_report`

## Module Hierarchy

| Name | Path | Type | Variables |
|------|------|------|-----------|
{chr(10).join(module_list)}

## Flowchart

```mermaid
{mermaid_code}
```

{deps_section}## Visual Graph

![Module Graph]({os.path.basename(png_path)})
"""

    with open(md_path, "w") as f:
        f.write(md_content)

    print(f"Saved module graph report to {md_path}")
    return md_path
