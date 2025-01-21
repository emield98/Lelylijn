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
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return IsochroneGeneratorAlgorithm()

    def name(self):
        return 'generateisochrones'

    def displayName(self):
        return self.tr('Generate Isochrones from Network')

    def group(self):
        return self.tr('Network Analysis')

    def groupId(self):
        return 'networkanalysis'

    def shortHelpString(self):
        return self.tr('Creates isochrones by generating concave hulls around '
                      'service access points that intersect with each network line.')

    def initAlgorithm(self, config=None):
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
                defaultValue=0.3,
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
        network_layer = self.parameterAsVectorLayer(parameters, self.INPUT_NETWORK, context)
        if network_layer is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_NETWORK))

        source_saps = self.parameterAsSource(parameters, self.INPUT_SAPS, context)
        if source_saps is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_SAPS))

        alpha = self.parameterAsDouble(parameters, self.ALPHA, context)

        fields = network_layer.fields()

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields, QgsWkbTypes.Polygon, network_layer.crs()
        )

        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        total = 100.0 / network_layer.featureCount() if network_layer.featureCount() else 0

        for current, network_feature in enumerate(network_layer.getFeatures()):
            if feedback.isCanceled():
                break

            feedback.setProgress(int(current * total))
            
            original_attributes = network_feature.attributes()

            temp_network = QgsVectorLayer(
                f"LineString?crs={network_layer.crs().authid()}&field=fid:integer&field=stop_name1:string&field=CLUSTER_ID:integer&field=type:string&field=start:string",
                "temp",
                "memory"
            )
            
            temp_network.startEditing()
            temp_feature = QgsFeature()
            temp_feature.setGeometry(network_feature.geometry())
            temp_feature.setAttributes(original_attributes)
            temp_network.addFeature(temp_feature)
            temp_network.commitChanges()

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

            if extracted_layer.featureCount() > 2:
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
                    
                    out_feat = QgsFeature(fields)
                    out_feat.setGeometry(hull_feature.geometry())
                    out_feat.setAttributes(original_attributes)
                    
                    sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

        return {self.OUTPUT: dest_id}