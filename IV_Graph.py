# -*- coding: utf-8 -*-
#
# Licensed under the terms of the MIT License
# Copyright (c) 2015 Pierre Raybaut

"""
Simple example illustrating Qt Charts capabilities to plot curves with 
a high number of points, using OpenGL accelerated series
"""

from PyQt5.QtChart import QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis
from PyQt5.QtGui import QPolygonF, QPainter, QBrush, QGradient, QLinearGradient, QColor, QFont, QPen
from PyQt5.QtCore import Qt, QDateTime, QDate, QTime, QPointF
from PyQt5.QtWidgets import QMainWindow

import numpy as np

import matplotlib.cm as cm

class IV_Graph(QChartView):
	def __init__(self, parent=None):
		super().__init__(parent=parent)

		self.chart = QChart()
		self.chart.layout().setContentsMargins(0, 0, 0, 0)
		self.chart.legend().hide()
		#self.chart.legend().setAlignment( Qt.AlignRight )

		self.setChart( self.chart )
		self.setRenderHint(QPainter.Antialiasing)
		#self.chart.setPlotAreaBackgroundBrush( QBrush(Qt.black) )
		#self.chart.setPlotAreaBackgroundVisible( True )

		self.graph_colors = cm.rainbow(np.linspace(0, 1, 10))

		self.xMin = -1.0
		self.xMax = 1.0
		self.yMin = 400
		self.yMax = 0
		self.graph_index = 0

		#self.chart.createDefaultAxes()
		x_axis = QValueAxis()
		x_axis.setTitleText( "Voltage (V)" )
		#x_axis = QDateTimeAxis()
		#x_axis.setTitleText( "Time" )
		#x_axis.setFormat("HH:mm:ss")
		#startDate = QDateTime.currentDateTime().addSecs( -5 * 60 )
		#endDate = QDateTime.currentDateTime().addSecs( 5 * 60 )
		#startDate = QDateTime(QDate(2017, 1, 9), QTime(17, 25, 0))
		#endDate = QDateTime(QDate(2017, 1, 9), QTime(17, 50, 0))
		self.chart.addAxis( x_axis, Qt.AlignBottom )
		#self.chart.axisX().setRange( startDate, endDate )
		self.chart.axisX().setRange( -1.0, 1.0 )

		y_axis = QValueAxis()
		y_axis.setTitleText( "Current (A)" )
		self.chart.addAxis( y_axis, Qt.AlignLeft )
		self.chart.axisY().setRange( -10E-3, 10E-3 )
		#self.chart.axisY().setRange( 260., 290. )

		#y_axis2 = QValueAxis()
		#y_axis2.setTitleText( "Heater Power (%)" )
		#self.chart.addAxis( y_axis2, Qt.AlignRight )
		#self.pidOutputSeries.attachAxis( y_axis2 )
		#y_axis2.setRange( 0, 100 )


		self.setRubberBand( QChartView.HorizontalRubberBand )

		# Customize chart title
		font = QFont()
		font.setPixelSize(24);
		self.chart.setTitleFont(font);
		#self.chart.setTitleBrush(QBrush(Qt.white));

		## Customize chart background
		#backgroundGradient = QLinearGradient()
		#backgroundGradient.setStart(QPointF(0, 0));
		#backgroundGradient.setFinalStop(QPointF(0, 1));
		#backgroundGradient.setColorAt(0.0, QColor(0x000147));
		#backgroundGradient.setColorAt(1.0, QColor(0x000117));
		#backgroundGradient.setCoordinateMode(QGradient.ObjectBoundingMode);
		#self.chart.setBackgroundBrush(backgroundGradient);
		transparent_background = QBrush(QColor(0,0,0,0))
		self.chart.setBackgroundBrush( transparent_background )

		# Customize axis label font
		labelsFont = QFont()
		labelsFont.setPixelSize(16);
		x_axis.setLabelsFont(labelsFont)
		y_axis.setLabelsFont(labelsFont)
		#y_axis2.setLabelsFont(labelsFont)
		x_axis.setTitleFont(labelsFont)
		y_axis.setTitleFont(labelsFont)
		#y_axis2.setTitleFont(labelsFont)

		# Customize axis colors
		#axisPen = QPen(QColor(0xd18952))
		axisPen = QPen(QColor(0x888888))
		axisPen.setWidth(2)
		x_axis.setLinePen(axisPen)
		y_axis.setLinePen(axisPen)
		#y_axis2.setLinePen(axisPen)

		## Customize axis label colors
		#axisBrush = QBrush(Qt.white)
		#x_axis.setLabelsBrush(axisBrush)
		#y_axis.setLabelsBrush(axisBrush)
		#y_axis2.setLabelsBrush(axisBrush)
		#x_axis.setTitleBrush(axisBrush)
		#y_axis.setTitleBrush(axisBrush)
		#y_axis2.setTitleBrush(axisBrush)

		## add the text label at the top:
		#textLabel = QCPItemText(customPlot);
		##textLabel.setPositionAlignment( Qt.AlignTop|Qt.AlignHCenter );
		#textLabel.position.setType(QCPItemPosition.ptAxisRectRatio);
		#textLabel.position.setCoords(0.5, 0); # place position at center/top of axis rect
		#textLabel.setText("Text Item Demo");
		#textLabel.setFont(QFont(font().family(), 16)); # make font a bit larger
		#textLabel.setPen(QPen(Qt.black)); # show black border around text

		## add the arrow:
		#self.arrow = QCPItemLine(customPlot);
		#self.arrow.start.setParentAnchor(textLabel.bottom);
		#self.arrow.end.setCoords(4, 1.6); # point to (4, 1.6) in x-y-plot coordinates
		#self.arrow.setHead(QCPLineEnding.esSpikeArrow);

	def set_title(self, title):
		self.chart.setTitle(title)

	def new_plot( self ):
		self.ivDataSeries = QLineSeries( self.chart )
		pen = self.ivDataSeries.pen()
		pen.setWidthF(2.)
		self.graph_index
#		print( *(255 * self.graph_colors[self.graph_index % 10]) )
		pen.setColor( QColor( *(255 * self.graph_colors[self.graph_index % 10]) ) )
		self.ivDataSeries.setPen( pen )
		#self.setpointTemperatureSeries.setUseOpenGL( True )
		self.chart.addSeries( self.ivDataSeries )

		self.ivDataSeries.attachAxis( self.chart.axisX() )
		self.ivDataSeries.attachAxis( self.chart.axisY() )
		self.ivDataSeries.pointAdded.connect( self.Rescale_Axes )

		self.graph_index += 1

	def add_new_data_point( self, x, y ):
		self.ivDataSeries.append( x, y )

		num_of_datapoints = self.ivDataSeries.count()
		self.repaint()

	#def Rescale_Axes2( self, index ):
	#	x = self.pidOutputSeries.at( index ).x()
	#	x_rescaled = False
	#	if( x < self.xMin ):
	#		self.xMin = x
	#		x_rescaled = True
	#	if( x > self.xMax ):
	#		self.xMax = x
	#		x_rescaled = True
	#	if( x_rescaled ):
	#		full_range = min( self.xMax - self.xMin, 5 * 60 * 1000 )
	#		margin = full_range * 0.05

	#		self.chart.axisX().setRange( QDateTime.fromMSecsSinceEpoch(self.xMax - full_range - margin), QDateTime.fromMSecsSinceEpoch(self.xMax + margin) )
			
	def Rescale_Axes( self, index ):
		x = self.ivDataSeries.at( index ).x()
		x_rescaled = False
		if( x < self.xMin ):
			self.xMin = x
			x_rescaled = True
		if( x > self.xMax ):
			self.xMax = x
			x_rescaled = True
		if( x_rescaled ):
			full_range = self.xMax - self.xMin
			margin = full_range * 0.05
			self.chart.axisX().setRange( self.xMin - margin, self.xMax + margin )

			#full_range = min( self.xMax - self.xMin, 5 * 60 * 1000 )
			#margin = full_range * 0.05
			#self.chart.axisX().setRange( QDateTime.fromMSecsSinceEpoch(self.xMax - full_range - margin), QDateTime.fromMSecsSinceEpoch(self.xMax + margin) )
			
		y = self.ivDataSeries.at( index ).y()
		y_rescaled = False
		if( y < self.yMin ):
			self.yMin = y
			y_rescaled = True
		if( y > self.yMax ):
			self.yMax = y
			y_rescaled = True
		if( y_rescaled ):
			full_range = self.yMax - self.yMin
			margin = full_range * 0.05
			self.chart.axisY().setRange( self.yMin - margin, self.yMax + margin )
			