# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PolygonCenterline
                                 A QGIS plugin
 Génère des centerlines à partir de polygones
                              -------------------
        begin                : 2025-04-07
        copyright            : (C) 2025
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDialog, QFormLayout, QComboBox, QDialogButtonBox, QSpinBox, QDoubleSpinBox, QCheckBox, QVBoxLayout, QLabel
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsField, QgsFeature, QgsGeometry, 
    QgsProcessingFeedback, QgsWkbTypes, QgsSpatialIndex, QgsFeatureRequest,
    QgsProcessingUtils, QgsMessageLog, QgsCoordinateReferenceSystem,
    NULL, QgsVectorFileWriter, QgsPointXY, QgsRectangle, QgsPoint
)
from qgis.core import QgsApplication, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterNumber, QgsProcessingParameterBoolean, QgsProcessingParameterVectorDestination
import os.path
import processing
from PyQt5.QtCore import QVariant
import numpy as np
from scipy.spatial import Voronoi
import math

class PolygonCenterlineDialog(QDialog):
    def __init__(self, iface):
        super(PolygonCenterlineDialog, self).__init__()
        self.iface = iface
        self.setupUI()
        
    def setupUI(self):
        self.setWindowTitle("Générateur de Centerlines")
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        # Sélection de la couche polygone
        self.layer_combo = QComboBox()
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == QgsVectorLayer.VectorLayer and layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                self.layer_combo.addItem(layer.name(), layer.id())
        form_layout.addRow("Couche de polygones:", self.layer_combo)
        
        # Paramètre de la méthode
        self.method_combo = QComboBox()
        self.method_combo.addItem("Squelettisation morphologique", "MORPHOLOGICAL")
        self.method_combo.addItem("Diagramme de Voronoï", "VORONOI")
        self.method_combo.addItem("Contour parallèle", "CONTOUR")
        form_layout.addRow("Méthode:", self.method_combo)
        
        # Paramètres de densification
        self.densify_check = QCheckBox("Densifier les polygones")
        self.densify_check.setChecked(True)
        form_layout.addRow(self.densify_check)
        
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 1000.0)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setSuffix(" unités")
        form_layout.addRow("Intervalle de densification:", self.interval_spin)
        
        # Paramètres de squelettisation
        self.simplify_check = QCheckBox("Simplifier les centerlines")
        self.simplify_check.setChecked(True)
        form_layout.addRow(self.simplify_check)
        
        self.tolerance_spin = QDoubleSpinBox()
        self.tolerance_spin.setRange(0.0001, 100.0)
        self.tolerance_spin.setValue(0.5)
        self.tolerance_spin.setSuffix(" unités")
        form_layout.addRow("Tolérance de simplification:", self.tolerance_spin)
        
        # Paramètres de pruning
        self.prune_check = QCheckBox("Élaguer les branches")
        self.prune_check.setChecked(True)
        form_layout.addRow(self.prune_check)
        
        self.min_length_spin = QDoubleSpinBox()
        self.min_length_spin.setRange(0.0, 1000.0)
        self.min_length_spin.setValue(5.0)
        self.min_length_spin.setSuffix(" unités")
        form_layout.addRow("Longueur minimale des branches:", self.min_length_spin)
        
        # Paramètres d'attributs
        self.copy_attributes = QCheckBox("Copier les attributs des polygones")
        self.copy_attributes.setChecked(True)
        form_layout.addRow(self.copy_attributes)
        
        layout.addLayout(form_layout)
        
        # Information d'aide
        help_text = QLabel("Ce plugin génère des centerlines à partir de polygones comme des rivières,\n"
                         "routes ou autres formes allongées. Pour des formes sinueuses,\n"
                         "utilisez la méthode 'Contour parallèle' avec une densification élevée.")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        
        # Boutons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
        self.setLayout(layout)

class PolygonCenterline:
    """QGIS Plugin pour générer des centerlines à partir de polygones"""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.tr('&Polygon Centerline')
        self.first_start = None

    def tr(self, message):
        return QCoreApplication.translate('PolygonCenterline', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)
        return action

    def initGui(self):
        """Créer les éléments de l'interface graphique"""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr('Générer Centerlines'),
            callback=self.run,
            parent=self.iface.mainWindow())

        self.first_start = True

    def unload(self):
        """Supprimer le menu et les icônes du plugin"""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr('&Polygon Centerline'),
                action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Exécuter le plugin lorsque l'utilisateur clique sur l'icône"""
        if self.first_start:
            self.first_start = False
            
        # Ouvrir la boîte de dialogue
        dlg = PolygonCenterlineDialog(self.iface)
        
        # Exécuter la boîte de dialogue
        if dlg.exec_():
            # Récupérer les paramètres
            layer_id = dlg.layer_combo.currentData()
            layer = QgsProject.instance().mapLayer(layer_id)
            
            if not layer:
                self.iface.messageBar().pushCritical(
                    "Erreur",
                    "Impossible de trouver la couche sélectionnée."
                )
                return
                
            # Paramètres
            method = dlg.method_combo.currentData()
            densify = dlg.densify_check.isChecked()
            interval = dlg.interval_spin.value()
            simplify = dlg.simplify_check.isChecked()
            tolerance = dlg.tolerance_spin.value()
            prune = dlg.prune_check.isChecked()
            min_length = dlg.min_length_spin.value()
            copy_attrs = dlg.copy_attributes.isChecked()
            
            # Générer les centerlines
            self.generate_centerlines(
                layer, method, densify, interval, simplify, tolerance, 
                prune, min_length, copy_attrs
            )
    
    def generate_centerlines(self, layer, method, densify, interval, simplify, tolerance, prune, min_length, copy_attrs):
        """Génère des centerlines à partir d'une couche de polygones"""
        self.iface.messageBar().pushInfo(
            "Centerline",
            "Génération des centerlines en cours..."
        )
        
        # Créer une couche temporaire pour stocker les résultats
        temp_layer = QgsVectorLayer("LineString?crs=" + layer.crs().authid(), "Centerlines", "memory")
        temp_provider = temp_layer.dataProvider()
        
        # Copier les champs source si demandé
        if copy_attrs:
            temp_provider.addAttributes(layer.fields())
            temp_layer.updateFields()
        
        # Traiter chaque polygone
        feature_count = layer.featureCount()
        for current, feature in enumerate(layer.getFeatures()):
            # Mettre à jour la barre de progression
            progress = int(current / feature_count * 100)
            self.iface.mainWindow().statusBar().showMessage(
                f"Traitement des polygones: {current+1}/{feature_count} ({progress}%)"
            )
            
            geom = feature.geometry()
            if geom.isEmpty() or geom.isNull():
                continue
                
            # Vérifier que c'est un polygone
            if geom.type() != QgsWkbTypes.PolygonGeometry:
                continue
            
            # Densifier le polygone si nécessaire
            if densify:
                geom = geom.densifyByDistance(interval)
            
            # Générer la centerline selon la méthode choisie
            centerline = None
            if method == "MORPHOLOGICAL":
                # Utiliser l'algorithme de squelettisation morphologique via GRASS
                try:
                    # Dans un cas réel, on appellerait l'algorithme GRASS v.thin
                    # Ici, on utilise notre implémentation de squelettisation
                    centerline = self.generate_morphological_skeleton(geom)
                except Exception as e:
                    self.iface.messageBar().pushWarning(
                        "Centerline",
                        f"Erreur lors de la squelettisation: {str(e)}"
                    )
                    continue
            
            elif method == "VORONOI":
                # Utiliser l'algorithme basé sur le diagramme de Voronoï
                try:
                    centerline = self.generate_voronoi_skeleton(geom)
                except Exception as e:
                    self.iface.messageBar().pushWarning(
                        "Centerline",
                        f"Erreur lors de la génération du diagramme de Voronoï: {str(e)}"
                    )
                    continue
                    
            else:  # CONTOUR
                # Utiliser l'algorithme de contour parallèle
                try:
                    centerline = self.generate_contour_centerline(geom)
                except Exception as e:
                    self.iface.messageBar().pushWarning(
                        "Centerline",
                        f"Erreur lors de la génération du contour parallèle: {str(e)}"
                    )
                    continue
            
            if not centerline or centerline.isEmpty():
                continue
                
            # Simplifier si demandé
            if simplify and not centerline.isEmpty():
                centerline = centerline.simplify(tolerance)
            
            # Élaguer si demandé
            if prune and not centerline.isEmpty():
                centerline = self.prune_branches(centerline, min_length)
            
            # Créer une nouvelle entité pour la centerline
            new_feat = QgsFeature()
            new_feat.setGeometry(centerline)
            
            # Copier les attributs si nécessaire
            if copy_attrs:
                new_feat.setAttributes(feature.attributes())
                
            temp_provider.addFeature(new_feat)
        
        # Réinitialiser la barre d'état
        self.iface.mainWindow().statusBar().clearMessage()
        
        # Si la couche est vide, sortir
        if temp_layer.featureCount() == 0:
            self.iface.messageBar().pushWarning(
                "Centerline",
                "Aucune centerline n'a pu être générée. Vérifiez les données d'entrée."
            )
            return
            
        # Ajouter la couche au projet
        QgsProject.instance().addMapLayer(temp_layer)
        
        self.iface.messageBar().pushSuccess(
            "Centerline",
            f"Génération terminée. {temp_layer.featureCount()} centerlines créées."
        )
    
    def generate_morphological_skeleton(self, geometry):
        """
        Génère un squelette morphologique à partir d'un polygone.
        Cette fonction utilise un algorithme de base pour simuler la squelettisation.
        Dans un plugin réel, on utiliserait GRASS v.thin ou un autre algorithme spécialisé.
        """
        # Dans un plugin réel, on pourrait appeler GRASS via processing:
        # params = {
        #     'input': QgsProcessingFeatureSourceDefinition(layer.id(), False),
        #     'output': 'memory:'
        # }
        # result = processing.run("grass7:v.thin", params)
        # return result['output']
        
        # Pour cette implémentation, on utilise une méthode simplifiée
        # qui calcule approximativement la ligne médiane
        # On divise le polygone en tranches verticales et on trouve le point central de chaque tranche
        
        # Extraire les coordonnées du contour du polygone
        if geometry.isMultipart():
            polygons = geometry.asMultiPolygon()
            # Prendre le plus grand polygone
            largest_polygon = polygons[0]
            max_area = QgsGeometry.fromPolygonXY([largest_polygon[0]]).area()
            
            for poly in polygons:
                area = QgsGeometry.fromPolygonXY([poly[0]]).area()
                if area > max_area:
                    largest_polygon = poly
                    max_area = area
            
            exterior_ring = largest_polygon[0]
        else:
            exterior_ring = geometry.asPolygon()[0]
        
        # Obtenir le rectangle englobant
        bbox = geometry.boundingBox()
        x_min = bbox.xMinimum()
        x_max = bbox.xMaximum()
        y_min = bbox.yMinimum()
        y_max = bbox.yMaximum()
        
        # Diviser le rectangle en tranches
        num_slices = max(50, int((x_max - x_min) / (bbox.height() * 0.05)))
        slice_width = (x_max - x_min) / num_slices
        
        # Points centraux pour chaque tranche
        centerline_points = []
        
        for i in range(num_slices + 1):
            x = x_min + i * slice_width
            
            # Créer une ligne verticale qui traverse le polygone
            line = QgsGeometry.fromPolylineXY([
                QgsPointXY(x, y_min - 10),
                QgsPointXY(x, y_max + 10)
            ])
            
            # Intersection avec le polygone
            intersection = line.intersection(geometry)
            
            if not intersection.isEmpty():
                if intersection.type() == QgsWkbTypes.LineGeometry:
                    # Si l'intersection est une ligne, prendre son milieu
                    if intersection.isMultipart():
                        # Prendre la ligne la plus longue
                        lines = intersection.asMultiPolyline()
                        longest_line = lines[0]
                        max_length = 0
                        for line in lines:
                            length = QgsGeometry.fromPolylineXY(line).length()
                            if length > max_length:
                                longest_line = line
                                max_length = length
                        
                        mid_point = QgsPointXY(
                            longest_line[0].x(),
                            (longest_line[0].y() + longest_line[-1].y()) / 2
                        )
                    else:
                        line_points = intersection.asPolyline()
                        mid_point = QgsPointXY(
                            line_points[0].x(),
                            (line_points[0].y() + line_points[-1].y()) / 2
                        )
                    
                    centerline_points.append(mid_point)
        
        # Créer la ligne à partir des points
        if len(centerline_points) > 1:
            return QgsGeometry.fromPolylineXY(centerline_points)
        else:
            return QgsGeometry()
    
    def generate_voronoi_skeleton(self, geometry):
        """
        Génère une centerline basée sur le diagramme de Voronoï.
        Cette méthode est particulièrement adaptée aux formes complexes.
        """
        # Pour un plugin réel, on appellerait un algorithme existant.
        # Ici, on développe une implémentation simplifiée.
        
        # Extraire les points du contour du polygone
        if geometry.isMultipart():
            polygons = geometry.asMultiPolygon()
            # Prendre le plus grand polygone
            largest_polygon = polygons[0]
            max_area = QgsGeometry.fromPolygonXY([largest_polygon[0]]).area()
            
            for poly in polygons:
                area = QgsGeometry.fromPolygonXY([poly[0]]).area()
                if area > max_area:
                    largest_polygon = poly
                    max_area = area
            
            boundary_points = largest_polygon[0]
        else:
            boundary_points = geometry.asPolygon()[0]
        
        # Convertir les points en tableau numpy pour Voronoi
        points = np.array([[p.x(), p.y()] for p in boundary_points])
        
        # Calculer le diagramme de Voronoï
        try:
            vor = Voronoi(points)
            
            # Extraire les segments Voronoï intérieurs
            centerline_segments = []
            
            for ridge_vertices in vor.ridge_vertices:
                if -1 not in ridge_vertices:  # Ignorer les segments infinis
                    # Obtenir les coordonnées des points
                    p1 = vor.vertices[ridge_vertices[0]]
                    p2 = vor.vertices[ridge_vertices[1]]
                    
                    # Créer un segment de ligne
                    segment = QgsGeometry.fromPolylineXY([
                        QgsPointXY(p1[0], p1[1]),
                        QgsPointXY(p2[0], p2[1])
                    ])
                    
                    # Vérifier que le segment est à l'intérieur du polygone
                    if geometry.contains(segment):
                        centerline_segments.append(segment)
            
            # Fusionner les segments pour former la centerline
            if centerline_segments:
                merged_lines = QgsGeometry.unaryUnion(centerline_segments)
                
                # Ne conserver que la plus longue ligne connectée
                if merged_lines.isMultipart():
                    lines = merged_lines.asMultiPolyline()
                    longest_line = lines[0]
                    max_length = QgsGeometry.fromPolylineXY(longest_line).length()
                    
                    for line in lines:
                        length = QgsGeometry.fromPolylineXY(line).length()
                        if length > max_length:
                            longest_line = line
                            max_length = length
                    
                    return QgsGeometry.fromPolylineXY(longest_line)
                else:
                    return merged_lines
            
        except Exception as e:
            # Si l'algorithme de Voronoï échoue, revenir à la méthode morphologique
            self.iface.messageBar().pushWarning(
                "Centerline",
                f"Erreur lors du calcul de Voronoï: {str(e)}. Utilisation de la méthode alternative."
            )
            return self.generate_morphological_skeleton(geometry)
        
        return QgsGeometry()
    
    def generate_contour_centerline(self, geometry):
        """
        Génère une centerline basée sur le retrait progressif des contours.
        Cette méthode est particulièrement adaptée aux formes allongées comme les rivières.
        """
        # Pour un plugin réel, on utiliserait des algorithmes optimisés.
        # Ici, on développe une implémentation simplifiée.
        
        # Obtenir le contour du polygone
        if geometry.isMultipart():
            polygons = geometry.asMultiPolygon()
            # Prendre le plus grand polygone
            largest_polygon = polygons[0]
            max_area = QgsGeometry.fromPolygonXY([largest_polygon[0]]).area()
            
            for poly in polygons:
                area = QgsGeometry.fromPolygonXY([poly[0]]).area()
                if area > max_area:
                    largest_polygon = poly
                    max_area = area
            
            current_geom = QgsGeometry.fromPolygonXY([largest_polygon[0]])
        else:
            current_geom = geometry.clone()
        
        # Calculer la distance de retrait basée sur la largeur approximative
        bbox = geometry.boundingBox()
        buffer_distance = min(bbox.width(), bbox.height()) * 0.1
        
        # Stocker le squelette en construction
        shrinking_polygons = []
        
        # Réduire progressivement le polygone
        max_iterations = 20  # Éviter les boucles infinies
        i = 0
        
        while i < max_iterations and not current_geom.isEmpty():
            shrinking_polygons.append(current_geom.clone())
            
            # Réduire le polygone
            current_geom = current_geom.buffer(-buffer_distance, 5, QgsGeometry.CapRound, QgsGeometry.JoinRound)
            
            # Si le polygone devient trop petit ou se divise, arrêter
            if current_geom.isEmpty() or current_geom.isMultipart():
                break
                
            i += 1
        
        # Extraire les centroïdes des polygones en rétrécissement
        centerline_points = []
        
        for poly in shrinking_polygons:
            center = poly.centroid().asPoint()
            centerline_points.append(center)
        
        # Si on n'a pas assez de points, utiliser une autre méthode
        if len(centerline_points) <= 2:
            return self.generate_morphological_skeleton(geometry)
        
        # Créer la ligne à partir des points centraux
        return QgsGeometry.fromPolylineXY(centerline_points)
    
    def prune_branches(self, centerline, min_length):
        """
        Élague les branches trop courtes de la centerline.
        Pour un plugin réel, on utiliserait des algorithmes de théorie des graphes.
        """
        if centerline.isEmpty():
            return centerline
            
        # Si la centerline est déjà une ligne simple, la renvoyer telle quelle
        if centerline.type() == QgsWkbTypes.LineGeometry and not centerline.isMultipart():
            return centerline
            
        # Si c'est une multiligne, ne garder que les segments assez longs
        if centerline.isMultipart():
            lines = centerline.asMultiPolyline()
            valid_lines = []
            
            for line in lines:
                line_geom = QgsGeometry.fromPolylineXY(line)
                if line_geom.length() >= min_length:
                    valid_lines.append(line)
            
            # S'il n'y a plus de lignes valides, renvoyer la plus longue
            if not valid_lines:
                longest_line = lines[0]
                max_length = QgsGeometry.fromPolylineXY(longest_line).length()
                
                for line in lines:
                    length = QgsGeometry.fromPolylineXY(line).length()
                    if length > max_length:
                        longest_line = line
                        max_length = length
                
                return QgsGeometry.fromPolylineXY(longest_line)
            
            if len(valid_lines) == 1:
                return QgsGeometry.fromPolylineXY(valid_lines[0])
            else:
                # Fusionner les lignes valides si possible
                multi_line = QgsGeometry.fromMultiPolylineXY(valid_lines)
                return multi_line
        
        return centerline
