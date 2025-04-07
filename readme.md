# QGIS Centerline Generator Plugin

A QGIS plugin that generates a **centerline (skeleton/medial axis)** from polygon or polyline geometries. Useful for cartographic simplification, hydrological modeling, urban planning, and spatial analysis.

## 🛰️ What It Does

- Extracts a centerline from selected polygon or line layers.
- Supports single or multi-feature layers.
- Optional simplification and smoothing.
- Outputs as a new vector layer (line geometry).

## 🧰 Requirements

- QGIS 3.x
- No external dependencies (uses PyQGIS and built-in geometry tools)

## 🛠️ Installation

### From ZIP

1. Download or clone this repository.
2. In QGIS, go to `Plugins > Manage and Install Plugins`.
3. Click **Install from ZIP**, select the downloaded file.
4. Activate the plugin from the plugin manager.

### From QGIS Plugin Repository (if published)

Search for **Centerline Generator** in the QGIS Plugin Manager and install it directly.

## 🚀 Usage

1. Load a polygon or polyline vector layer in QGIS.
2. Go to `Plugins > Centerline Generator > Generate Centerline`.
3. Choose:
   - **Input layer**
   - **Simplification tolerance** *(optional)*
   - **Output file location*
4. Click **Run** – a new line layer will be created as the centerline.

## ⚙️ Parameters

| Parameter               | Description                                      |
|-------------------------|--------------------------------------------------|
| Input Layer             | The vector layer to extract centerlines from    |
| Simplification Tolerance| Simplifies geometry before processing (optional)|
| Output Layer            | Path to save the resulting centerline layer     |

## 📸 Example

![screenshot](docs/centerline_example.png)

## 💡 Notes

- Works best with elongated or organic polygon shapes (e.g. rivers, roads, parcels).
- Based on Voronoi diagram and medial axis extraction.
- May struggle with very complex or self-intersecting shapes — try simplifying first.

## 📍 Roadmap

- [ ] Batch processing multiple features
- [ ] Support for multi-part geometries
- [ ] Customizable snapping and smoothing

## 🤝 Contributing

Contributions are welcome! Feel free to fork the repo, open issues, or submit pull requests.

## 📄 License

Licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.
