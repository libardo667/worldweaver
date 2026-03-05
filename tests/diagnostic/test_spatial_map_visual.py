#!/usr/bin/env python3
# ruff: noqa: E402
"""
Visual Spatial Map Test - Generate an HTML visualization of storylet positions and connections.

This creates a visual map showing:
- All storylets positioned in 2D space
- Connection lines between storylets
- Location requirements and choice outcomes
- Interactive hover details

Run this after generating a new database to see the spatial layout.
"""

import sys
from pathlib import Path
from typing import List

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.database import SessionLocal
from src.services.spatial_navigator import SpatialNavigator, Position
from src.models import Storylet


def generate_visual_map() -> str:
    """Generate an HTML visualization of the spatial storylet map."""

    with SessionLocal() as db:
        spatial_nav = SpatialNavigator(db)

        # Get all storylets with their data
        storylets = db.query(Storylet).all()
        storylet_data = []

        for s in storylets:
            text_val = str(s.text_template)
            storylet_data.append(
                {
                    "id": s.id,
                    "title": s.title,
                    "text": (text_val[:100] + "..." if len(text_val) > 100 else text_val),
                    "requires": s.requires or {},
                    "choices": s.choices or [],
                    "weight": s.weight or 1.0,
                }
            )

        # Assign positions if not already done
        if not spatial_nav.storylet_positions:
            print("🔧 Assigning spatial positions...")
            spatial_nav.assign_spatial_positions(storylet_data)

        # Get map bounds
        if not spatial_nav.storylet_positions:
            print("❌ No storylets positioned!")
            return "<h1>No storylets found or positioned</h1>"

        positions = list(spatial_nav.storylet_positions.values())
        min_x = min(pos.x for pos in positions) - 1
        max_x = max(pos.x for pos in positions) + 1
        min_y = min(pos.y for pos in positions) - 1
        max_y = max(pos.y for pos in positions) + 1

        width = max_x - min_x
        height = max_y - min_y

        # Scale for display
        cell_size = 120
        margin = 60
        svg_width = width * cell_size + 2 * margin
        svg_height = height * cell_size + 2 * margin

        def pos_to_svg(pos: Position) -> tuple[float, float]:
            """Convert grid position to SVG coordinates."""
            x = (pos.x - min_x) * cell_size + margin
            y = (pos.y - min_y) * cell_size + margin
            return x, y

        # Build connections map
        connections: List[tuple[int, int, str]] = []
        for storylet in storylet_data:
            source_id = storylet["id"]
            source_pos = spatial_nav.storylet_positions.get(source_id)
            if not source_pos:
                continue

            for choice in storylet["choices"]:
                # Handle both 'set' and 'set_vars'
                choice_set = choice.get("set") or choice.get("set_vars") or {}
                target_location = choice_set.get("location")

                if target_location:
                    # Find storylets that require this location
                    for target_storylet in storylet_data:
                        target_requires = target_storylet.get("requires", {})
                        if target_requires.get("location") == target_location:
                            target_id = target_storylet["id"]
                            target_pos = spatial_nav.storylet_positions.get(target_id)
                            if target_pos:
                                connections.append(
                                    (
                                        source_id,
                                        target_id,
                                        choice.get("label", "Continue"),
                                    )
                                )

        # Generate HTML
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Spatial Storylet Map</title>
    <style>
        body {{
            font-family: 'Segoe UI', sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 100%;
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        .stat {{
            text-align: center;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }}
        .map-container {{
            text-align: center;
            overflow: auto;
            border: 2px solid #ddd;
            border-radius: 8px;
            background: linear-gradient(45deg, #f8f9fa 25%, transparent 25%), 
                        linear-gradient(-45deg, #f8f9fa 25%, transparent 25%), 
                        linear-gradient(45deg, transparent 75%, #f8f9fa 75%), 
                        linear-gradient(-45deg, transparent 75%, #f8f9fa 75%);
            background-size: 20px 20px;
            background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
        }}
        .storylet {{
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        .storylet:hover {{
            transform: scale(1.1);
        }}
        .storylet-node {{
            fill: #667eea;
            stroke: #fff;
            stroke-width: 3;
        }}
        .storylet-text {{
            fill: white;
            font-size: 12px;
            font-weight: bold;
            text-anchor: middle;
            dominant-baseline: central;
            pointer-events: none;
        }}
        .connection {{
            stroke: #feca57;
            stroke-width: 2;
            fill: none;
            marker-end: url(#arrowhead);
            opacity: 0.7;
        }}
        .tooltip {{
            position: absolute;
            background: rgba(0,0,0,0.9);
            color: white;
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
            max-width: 300px;
            z-index: 1000;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
        }}
        .legend {{
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        .legend-item {{
            display: inline-flex;
            align-items: center;
            margin-right: 20px;
            margin-bottom: 5px;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🗺️ Spatial Storylet Map</h1>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{len(storylets)}</div>
                <div class="stat-label">Total Storylets</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len(spatial_nav.storylet_positions)}</div>
                <div class="stat-label">Positioned</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len(connections)}</div>
                <div class="stat-label">Connections</div>
            </div>
            <div class="stat">
                <div class="stat-value">{width}×{height}</div>
                <div class="stat-label">Grid Size</div>
            </div>
        </div>
        
        <div class="map-container">
            <svg width="{svg_width}" height="{svg_height}" id="map-svg">
                <defs>
                    <marker id="arrowhead" markerWidth="10" markerHeight="7" 
                            refX="9" refY="3.5" orient="auto">
                        <polygon points="0 0, 10 3.5, 0 7" fill="#feca57" />
                    </marker>
                </defs>
                
                <!-- Grid lines -->
                <defs>
                    <pattern id="grid" width="{cell_size}" height="{cell_size}" patternUnits="userSpaceOnUse">
                        <path d="M {cell_size} 0 L 0 0 0 {cell_size}" fill="none" stroke="#ddd" stroke-width="1"/>
                    </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid)" opacity="0.5" />
                
                <!-- Connections -->
        """

        for source_id, target_id, choice_label in connections:
            source_pos = spatial_nav.storylet_positions[source_id]
            target_pos = spatial_nav.storylet_positions[target_id]

            sx, sy = pos_to_svg(source_pos)
            tx, ty = pos_to_svg(target_pos)

            # Add some curve to avoid overlapping lines
            mid_x = (sx + tx) / 2
            mid_y = (sy + ty) / 2 - 20

            html += f"""
                <path class="connection" d="M {sx},{sy} Q {mid_x},{mid_y} {tx},{ty}"
                      data-choice="{choice_label}" />
            """

        html += "\n                <!-- Storylets -->"

        for storylet in storylet_data:
            storylet_id = storylet["id"]
            pos = spatial_nav.storylet_positions.get(storylet_id)
            if not pos:
                continue

            x, y = pos_to_svg(pos)

            # Determine storylet color based on requirements
            requires = storylet.get("requires", {})
            if "location" in requires:
                color = "#27ae60"  # Green for location-based
            elif "danger" in requires:
                color = "#e74c3c"  # Red for danger-based
            elif requires:
                color = "#f39c12"  # Orange for other requirements
            else:
                color = "#667eea"  # Blue for no requirements

            # Truncate title for display
            display_title = storylet["title"][:12] + ("..." if len(storylet["title"]) > 12 else "")

            # Escape for HTML
            tooltip_text = f"Title: {storylet['title']}\\n" f"ID: {storylet_id}\\n" f"Position: ({pos.x}, {pos.y})\\n" f"Requires: {requires}\\n" f"Choices: {len(storylet['choices'])}\\n" f"Weight: {storylet['weight']}"

            html += f"""
                <g class="storylet" data-id="{storylet_id}" data-tooltip="{tooltip_text}">
                    <circle cx="{x}" cy="{y}" r="25" class="storylet-node" fill="{color}" />
                    <text x="{x}" y="{y}" class="storylet-text">{display_title}</text>
                </g>
            """

        html += """
            </svg>
        </div>
        
        <div class="legend">
            <h3>Legend</h3>
            <div class="legend-item">
                <div class="legend-color" style="background: #27ae60;"></div>
                <span>Location-based storylets</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #e74c3c;"></div>
                <span>Danger-based storylets</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #f39c12;"></div>
                <span>Other requirements</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #667eea;"></div>
                <span>No requirements</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #feca57;"></div>
                <span>Choice connections (arrows)</span>
            </div>
        </div>
        
        <div class="tooltip" id="tooltip"></div>
    </div>
    
    <script>
        const tooltip = document.getElementById('tooltip');
        const storylets = document.querySelectorAll('.storylet');
        
        storylets.forEach(storylet => {
            storylet.addEventListener('mouseenter', (e) => {
                const tooltipText = e.currentTarget.getAttribute('data-tooltip');
                tooltip.innerHTML = tooltipText.replace(/\\n/g, '<br>');
                tooltip.style.opacity = '1';
            });
            
            storylet.addEventListener('mousemove', (e) => {
                tooltip.style.left = e.pageX + 10 + 'px';
                tooltip.style.top = e.pageY + 10 + 'px';
            });
            
            storylet.addEventListener('mouseleave', () => {
                tooltip.style.opacity = '0';
            });
        });
    </script>
</body>
</html>
        """

        return html


def main():
    """Generate and save the visual map."""
    print("🗺️ Generating Spatial Storylet Map...")

    html_content = generate_visual_map()

    # Save to file in reports/
    reports_dir = project_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_file = reports_dir / "spatial_map.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Map saved to: {output_file}")
    print(f"🌐 Open in browser: file://{output_file.absolute()}")

    # Browser auto-open removed per user request


if __name__ == "__main__":
    main()
