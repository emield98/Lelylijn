from qgis.core import QgsProject, QgsField, QgsVectorLayer, QgsFeature, QgsTask, QgsApplication, QgsGeometry
from PyQt5.QtCore import QVariant
import processing
import gc

class ProcessPOITask(QgsTask):
    def __init__(self, poi_layer, road_network, lelylijn_layer, output_layer, description="Processing POIs"):
        super().__init__(description)
        self.poi_layer = poi_layer
        self.road_network = road_network
        self.lelylijn_layer = lelylijn_layer
        self.output_layer = output_layer
        self.output_provider = output_layer.dataProvider()
        self.total_pois = len([f for f in poi_layer.getFeatures()])
        self.progress = 0

    def update_progress(self, step=1):
        self.progress += step
        self.setProgress((self.progress / self.total_pois) * 100)

    def run(self):
        try:
            # Enable editing mode
            self.output_layer.startEditing()

            def process_layer(layer_name, sap_layer, max_distance):
                for poi_feature in self.poi_layer.getFeatures():
                    # Get the geometry and ID of the POI
                    geometry = poi_feature.geometry()
                    poi_id = poi_feature['fid']

                    if not geometry.isGeosValid():
                        continue

                    # Create a buffer around the POI
                    buffer_geometry = geometry.buffer(max_distance, 5)

                    # Create a temporary buffer layer
                    buffer_layer = QgsVectorLayer(f"Polygon?crs={self.poi_layer.crs().authid()}", f"{layer_name}_Buffer_{poi_id}", "memory")
                    buffer_provider = buffer_layer.dataProvider()

                    buffer_feature = QgsFeature()
                    buffer_feature.setGeometry(buffer_geometry)
                    buffer_provider.addFeature(buffer_feature)
                    buffer_layer.updateExtents()

                    # Clip the SAP layer using the buffer
                    sap_clip_parameters = {
                        'INPUT': sap_layer.source(),
                        'OVERLAY': buffer_layer,
                        'OUTPUT': 'TEMPORARY_OUTPUT'
                    }
                    sap_clip_result = processing.run("native:clip", sap_clip_parameters)
                    clipped_sap_layer = sap_clip_result['OUTPUT']

                    # Clip the road network using the buffer layer
                    clip_parameters = {
                        'INPUT': self.road_network.source(),
                        'OVERLAY': buffer_layer,
                        'OUTPUT': 'TEMPORARY_OUTPUT'
                    }
                    clip_result = processing.run("native:clip", clip_parameters)
                    clipped_road_network = clip_result['OUTPUT']

                    # Prepare the Service Area tool parameters
                    service_area_parameters = {
                        'INPUT': clipped_road_network,
                        'STRATEGY': 0,
                        'DIRECTION_FIELD': '',
                        'VALUE_FORWARD': '',
                        'VALUE_BACKWARD': '',
                        'VALUE_BOTH': '',
                        'DEFAULT_DIRECTION': 2,
                        'SPEED_FIELD': '',
                        'DEFAULT_SPEED': 50,
                        'TOLERANCE': 0,
                        'START_POINT': f"{geometry.asPoint().x()},{geometry.asPoint().y()} [EPSG:{self.poi_layer.crs().postgisSrid()}]",
                        'TRAVEL_COST2': max_distance,
                        'INCLUDE_BOUNDS': False,
                        'OUTPUT_LINES': 'TEMPORARY_OUTPUT'
                    }

                    service_area_result = processing.run("native:serviceareafrompoint", service_area_parameters)
                    service_area_layer = service_area_result['OUTPUT_LINES']

                    # Join SAPs to the network using `native:joinbynearest`
                    join_parameters = {
                        'INPUT': clipped_sap_layer,
                        'INPUT_2': service_area_layer,
                        'FIELDS_TO_COPY': [],
                        'DISCARD_NONMATCHING': True,
                        'PREFIX': '',
                        'NEIGHBORS': 1,
                        'MAX_DISTANCE': 1,
                        'OUTPUT': 'TEMPORARY_OUTPUT',
                    }

                    join_result = processing.run("native:joinbynearest", join_parameters)
                    joined_layer = join_result['OUTPUT']

                    # Track already calculated distances to optimize performance
                    calculated_distances = {}

                    # Create separate rows for each SAP
                    for sap_feature in joined_layer.getFeatures():
                        sap_id = sap_feature['fid']
                        sap_attributes = sap_feature.attributes()
                        sap_geometry = sap_feature.geometry()

                        # Check if the distance to this SAP geometry has already been calculated
                        sap_geometry_wkt = sap_geometry.asWkt()
                        if sap_geometry_wkt in calculated_distances:
                            distance = calculated_distances[sap_geometry_wkt]
                        else:
                            # Calculate distance from POI to SAP along the network
                            distance_parameters = {
                                'INPUT': clipped_road_network,
                                'DEFAULT_DIRECTION': 2,
                                'STRATEGY': 0,
                                'START_POINT': geometry.asPoint(),
                                'END_POINT': sap_geometry.asPoint(),
                                'OUTPUT': 'TEMPORARY_OUTPUT'
                            }

                            try:
                                distance_result = processing.run("native:shortestpathpointtopoint", distance_parameters)
                                distance_layer = distance_result['OUTPUT']
                                distance_feature = next(distance_layer.getFeatures(), None)
                                distance = distance_feature['cost'] if distance_feature and 'cost' in distance_feature.fields().names() else -1
                            except Exception:
                                distance = -1

                            # Store the calculated distance
                            calculated_distances[sap_geometry_wkt] = distance

                        # Skip SAPs beyond the maximum distance
                        if distance > max_distance:
                            continue

                        # Create a new feature with the POI geometry and SAP attributes
                        new_feature = QgsFeature(self.output_layer.fields())
                        new_feature.setGeometry(geometry)
                        new_feature.setAttributes([poi_id] + [distance] + sap_attributes)
                        self.output_provider.addFeature(new_feature)

                    # Commit changes to the output layer after processing each POI
                    self.output_layer.commitChanges()
                    self.output_layer.startEditing()

                    # Explicitly free memory
                    buffer_layer = None
                    clipped_sap_layer = None
                    clipped_road_network = None
                    service_area_layer = None
                    joined_layer = None
                    gc.collect()

                    # Update progress
                    self.update_progress()

            # Process Lelylijn stops
            process_layer("lelylijn", self.lelylijn_layer, 3000)

            return True
        except Exception:
            return False

    def finished(self, result):
        if result:
            QgsProject.instance().addMapLayer(self.output_layer)

# Main script
poi_layer = QgsProject.instance().mapLayersByName('POI')[0]
road_network = QgsProject.instance().mapLayersByName('hartlijn_fiets_voet')[0]
lelylijn_layer = QgsProject.instance().mapLayersByName('Lelylijn_sc1')[0] # Change this to the correct layer name

# Create a new output layer for the results
output_layer = QgsVectorLayer(f"Point?crs={poi_layer.crs().authid()}", "POI_SAP_Relationships", "memory")
output_provider = output_layer.dataProvider()

# Add fields from the POI and SAP layers
poi_fields = [QgsField("POI_ID", QVariant.Int)]
sap_fields = [QgsField(field.name(), field.type()) for field in lelylijn_layer.fields()]
distance_field = [QgsField("Distance", QVariant.Double)]
output_provider.addAttributes(poi_fields + distance_field + sap_fields)
output_layer.updateFields()

# Create and schedule the task
task = ProcessPOITask(poi_layer, road_network, lelylijn_layer, output_layer)
QgsApplication.taskManager().addTask(task)
