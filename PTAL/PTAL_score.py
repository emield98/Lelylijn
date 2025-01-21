from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsField,
    QgsFeature,
    QgsVectorDataProvider
)
from PyQt5.QtCore import QVariant

# Load the base POI layer
poi_layer_name = 'POI'  # Replace with your actual POI layer name
poi_layer = QgsProject.instance().mapLayersByName(poi_layer_name)[0]

if not poi_layer:
    raise Exception(f"Layer '{poi_layer_name}' not found!")

# Load the relationships layer
relationships_layer_name = 'POI_SAP_Relationships'  # Replace with your actual relationships layer name
relationships_layer = QgsProject.instance().mapLayersByName(relationships_layer_name)[0]

if not relationships_layer:
    raise Exception(f"Layer '{relationships_layer_name}' not found!")

# Create a new layer for PTAL with the same CRS and geometry type as the POI layer
crs = poi_layer.crs().authid()  # Get the CRS of the POI layer
geometry_type = "Point"  # Assuming the POI layer is a point layer
ptal_layer = QgsVectorLayer(f"{geometry_type}?crs={crs}", "PTAL", "memory")
provider = ptal_layer.dataProvider()
provider.addAttributes([
    QgsField("POI_ID", QVariant.Int),
    QgsField("AI_bus", QVariant.Double),
    QgsField("AI_trein", QVariant.Double),
    QgsField("PTAI", QVariant.Double)
])
ptal_layer.updateFields()

# Group features by POI_ID and route_type in the relationships layer
def calculate_ai(features):
    edf_values = [f["EDF"] for f in features if f["EDF"] is not None]
    if not edf_values:
        return 0
    largest_edf = max(edf_values)
    remaining_sum = sum(edf_values) - largest_edf
    return largest_edf + 0.5 * remaining_sum

relationships_groups = {}
for feature in relationships_layer.getFeatures():
    poi_id = feature["POI_ID"]
    route_type = feature["route_type"].lower() if feature["route_type"] else None
    if poi_id not in relationships_groups:
        relationships_groups[poi_id] = {"bus": [], "trein": []}
    if route_type == "bus":
        relationships_groups[poi_id]["bus"].append(feature)
    elif route_type == "trein":
        relationships_groups[poi_id]["trein"].append(feature)

# Calculate AI and PTAI for each POI_ID in the POI layer
for poi_feature in poi_layer.getFeatures():
    poi_id = poi_feature["fid"]
    geometry = poi_feature.geometry()

    groups = relationships_groups.get(poi_id, {"bus": [], "trein": []})  # Default to empty groups if missing
    ai_bus = calculate_ai(groups["bus"])
    ai_trein = calculate_ai(groups["trein"])
    ptai = ai_bus + ai_trein

    # Add a new feature to the PTAL layer
    new_feature = QgsFeature(ptal_layer.fields())
    new_feature.setGeometry(geometry)
    new_feature.setAttributes([poi_id, ai_bus, ai_trein, ptai])
    provider.addFeature(new_feature)

# Add the new PTAL layer to the project
QgsProject.instance().addMapLayer(ptal_layer)

print("PTAL layer created with columns POI_ID, AI_bus, AI_trein, and PTAI using POI layer as base.")
