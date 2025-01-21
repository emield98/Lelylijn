from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsField,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsEditorWidgetSetup
)
from PyQt5.QtCore import QVariant

# Load the layer (replace 'POI_SAP_Relationships' with your actual layer name if different)
layer_name = 'POI_SAP_Relationships'
layer = QgsProject.instance().mapLayersByName(layer_name)[0]

if not layer:
    raise Exception(f"Layer '{layer_name}' not found!")

# Add a new field 'transport_mode'
if not layer.fields().indexFromName('transport_mode') >= 0:
    layer.dataProvider().addAttributes([
        QgsField('transport_mode', QVariant.String)
    ])
    layer.updateFields()

# Add a new field 'travel_time'
if not layer.fields().indexFromName('TT') >= 0:
    layer.dataProvider().addAttributes([
        QgsField('TT', QVariant.Double)
    ])
    layer.updateFields()

# Add a new field 'SWT'
if not layer.fields().indexFromName('SWT') >= 0:
    layer.dataProvider().addAttributes([
        QgsField('SWT', QVariant.Double)
    ])
    layer.updateFields()

# Add a new field 'AWT'
if not layer.fields().indexFromName('AWT') >= 0:
    layer.dataProvider().addAttributes([
        QgsField('AWT', QVariant.Double)
    ])
    layer.updateFields()

# Add a new field 'TAT'
if not layer.fields().indexFromName('TAT') >= 0:
    layer.dataProvider().addAttributes([
        QgsField('TAT', QVariant.Double)
    ])
    layer.updateFields()

# Add a new field 'EDF'
if not layer.fields().indexFromName('EDF') >= 0:
    layer.dataProvider().addAttributes([
        QgsField('EDF', QVariant.Double)
    ])
    layer.updateFields()

# Define the logic for assigning transport modes, calculating travel time, SWT, AWT, TAT, and EDF
def assign_transport_mode_and_time(feature):
    route_type = feature['route_type'].lower() if feature['route_type'] else ''
    distance = feature['Distance']
    frequency = feature['frequency']

    transport_mode = None
    travel_time = None
    swt = None
    awt = None
    tat = None
    edf = None

    if route_type == 'bus':
        transport_mode = 'walking'
        travel_time = distance / 80  # Walking speed in meters per minute

    elif route_type == 'trein':
        if distance <= 800:
            transport_mode = 'walking'
            travel_time = distance / 80  # Walking speed in meters per minute
        else:
            transport_mode = 'cycling'
            travel_time = distance / 300  # Cycling speed in meters per minute

    # Calculate SWT
    if frequency > 0:
        swt = 0.5 * (60 / frequency)

    # Calculate AWT
    if swt is not None:
        if route_type == 'trein':
            awt = swt + 0.75
        else:
            awt = swt + 2

    # Calculate TAT
    if travel_time is not None and awt is not None:
        tat = travel_time + awt

    # Calculate EDF
    if tat is not None and tat > 0:
        edf = 0.5 * (60 / tat)

    return transport_mode, travel_time, swt, awt, tat, edf

# Start an editing session
layer.startEditing()

# Update the 'transport_mode', 'travel_time', 'SWT', 'AWT', 'TAT', and 'EDF' fields for each feature
for feature in layer.getFeatures():
    transport_mode, travel_time, swt, awt, tat, edf = assign_transport_mode_and_time(feature)
    if transport_mode:
        feature['transport_mode'] = transport_mode
    feature['TT'] = travel_time
    feature['SWT'] = swt
    feature['AWT'] = awt
    feature['TAT'] = tat
    feature['EDF'] = edf
    layer.updateFeature(feature)

# Save changes
layer.commitChanges()

print("Transport mode, travel time, SWT, AWT, TAT, and EDF columns added and updated successfully!")
