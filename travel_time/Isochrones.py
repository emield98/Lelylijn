import time
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterNumber,
                       QgsWkbTypes,
                       QgsFeature,
                       QgsVectorLayer,
                       QgsFields,
                       QgsField)
from qgis.PyQt.QtCore import QVariant
from qgis import processing

class IsochroneGeneratorAlgorithm(QgsProcessingAlgorithm):
    INPUT_NETWORK = 'INPUT_NETWORK'
    INPUT_SAPS = 'INPUT_SAPS'
    ALPHA = 'ALPHA'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        # Translate the given string
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        # Create a new instance of the algorithm
        return IsochroneGeneratorAlgorithm()

    def name(self):
        # Return the algorithm name
        return 'generateisochrones'

    def displayName(self):
        # Return the display name of the algorithm
        return self.tr('Generate Isochrones from Network')

    def group(self):
        # Return the group name
        return self.tr('Network Analysis')

    def groupId(self):
        # Return the group ID
        return 'networkanalysis'

    def shortHelpString(self):
        # Return a short help string for the algorithm
        return self.tr('Creates isochrones by generating concave hulls around '
                      'service access points that intersect with each network line.')

    def initAlgorithm(self, config=None):
        # Initialize the algorithm parameters
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_NETWORK,
                self.tr('Network Lines Layer'),
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_SAPS,
                self.tr('Service Access Points Layer'),
                [QgsProcessing.TypeVectorPoint]
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.ALPHA,
                self.tr('Concave Hull Alpha (0.0-1.0)'),
                QgsProcessingParameterNumber.Double,
                defaultValue=0.05,
                minValue=0.0,
                maxValue=1.0
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output Isochrones')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # Retrieve the input network layer
        network_layer = self.parameterAsVectorLayer(parameters, self.INPUT_NETWORK, context)
        if network_layer is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_NETWORK))

        # Retrieve the input service access points layer
        source_saps = self.parameterAsSource(parameters, self.INPUT_SAPS, context)
        if source_saps is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_SAPS))

        # Retrieve the alpha parameter
        alpha = self.parameterAsDouble(parameters, self.ALPHA, context)

        # Get the fields from the network layer
        fields = network_layer.fields()

        # Adding a new field to store the count of the extracted points
        count_field = QgsField("point_count", QVariant.Int)
        fields.append(count_field)

        # Create the output sink
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields, QgsWkbTypes.Polygon, network_layer.crs()
        )

        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        # Calculate the progress step
        total = 100.0 / network_layer.featureCount() if network_layer.featureCount() else 0

        # Iterate over each feature in the network layer
        for current, network_feature in enumerate(network_layer.getFeatures()):
            if feedback.isCanceled():
                break

            # Update the progress
            feedback.setProgress(int(current * total))

            # Get the original attributes of the network feature
            original_attributes = network_feature.attributes()

            # Create a temporary network layer
            temp_network = QgsVectorLayer(
                f"LineString?crs={network_layer.crs().authid()}&field=fid:integer&field=stop_name1:string&field=CLUSTER_ID:integer&field=type:string&field=start:string",
                "temp",
                "memory"
            )

            # Start editing the temporary network layer
            temp_network.startEditing()
            temp_feature = QgsFeature()
            temp_feature.setGeometry(network_feature.geometry())
            temp_feature.setAttributes(original_attributes)
            temp_network.addFeature(temp_feature)
            temp_network.commitChanges()

            # Extract points that intersect with the temporary network layer
            extracted_result = processing.run(
                "native:extractbylocation",
                {
                    'INPUT': parameters[self.INPUT_SAPS],
                    'PREDICATE': [0],
                    'INTERSECT': temp_network,
                    'OUTPUT': 'memory:'
                },
                context=context,
                feedback=feedback
            )

            extracted_layer = extracted_result['OUTPUT']

            # Count the number of extracted points
            point_count = extracted_layer.featureCount()

            if point_count > 2:
                # Generate a concave hull from the extracted points
                hull_result = processing.run(
                    "native:concavehull",
                    {
                        'INPUT': extracted_layer,
                        'ALPHA': alpha,
                        'HOLES': False,
                        'OUTPUT': 'memory:'
                    },
                    context=context,
                    feedback=feedback
                )

                hull_layer = hull_result['OUTPUT']

                if hull_layer.featureCount() > 0:
                    hull_feature = next(hull_layer.getFeatures())

                    # Create a new feature for the output layer
                    out_feat = QgsFeature(fields)
                    out_feat.setGeometry(hull_feature.geometry())
                    out_feat.setAttributes(original_attributes + [point_count])

                    # Add the feature to the output sink
                    sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

            # Introduce a delay
            time.sleep(0.1)  # Adjust the sleep duration as needed

        # Return the output layer ID
        return {self.OUTPUT: dest_id}
