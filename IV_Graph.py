# -*- coding: utf-8 -*-
#
# Licensed under the terms of the MIT License
# Copyright (c) 2015 Pierre Raybaut

"""
Simple example illustrating Qt Charts capabilities to plot curves with 
a high number of points, using OpenGL accelerated series
"""

#from PyQt5.QtChart import QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis
from PyQt5.QtGui import QPolygonF, QPainter, QBrush, QGradient, QLinearGradient, QColor, QFont, QPen
from PyQt5.QtCore import Qt, QDateTime, QDate, QTime, QPointF
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout

import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.animation as animation

import numpy as np

import matplotlib.cm as cm

class IV_Graph( QWidget ):
	def __init__(self, parent=None):
		super().__init__(parent=parent)

		self.current_graph_data = []
		self.current_graph = None
		#self.graph_colors = cm.get_cmap('seismic')(np.linspace(0, 1, 10))
		self.graph_colors = cm.rainbow(np.linspace(0, 1, 10))
		# a figure instance to plot on
		self.figure = plt.figure()
		# this is the Canvas Widget that displays the `figure`
		# it takes the `figure` instance as a parameter to __init__
		self.canvas = FigureCanvas( self.figure )
		# this is the Navigation widget
		# it takes the Canvas widget and a parent
		self.toolbar = NavigationToolbar( self.canvas, self )
		# set the layout
		plt.ion()
		layout = QVBoxLayout()
		layout.addWidget(self.canvas)
		layout.addWidget(self.toolbar)
		self.setLayout(layout)


		self.ax = self.figure.add_subplot(111)
		self.ax.set_xlabel( 'Bias (V)' )
		self.ax.set_ylabel( 'Current (A)' )
		self.ax.set_title( 'I-V' )
		self.figure.tight_layout()
		#self.ax.plot( [1,2,3,4], [1,2,3,4], 'b-')
		self.all_graphs = []
		self.debug_counter = 0
		#self.current_graph, = self.ax.plot( [], [], 'b-')
		#self.canvas.show()

	def new_plot( self ):
		#self.current_graph, = self.ax.plot( [1,2,3,4], [1,2,3,4], 'b-')
		#cm.get_cmap('seismic')(np.linspace(0, 1, 6)
		self.current_graph, = self.ax.plot( [], [], color=self.graph_colors[self.debug_counter])
		self.running_graph, = self.ax.plot( [], [], 'ro-' )
		self.debug_counter = (self.debug_counter + 1) % 10
		self.all_graphs.append( self.current_graph )
		#self.ax.set_xlim([50,100])
		#self.current_graph_data = [(2,3),(4,5)]
		self.current_graph_data = []
		self.newest_data = None
		self.ani = animation.FuncAnimation(self.figure, self.replot, blit=False, interval=10,
                              repeat=True)

	def replot( self, frame_number ):
		if len( self.current_graph_data ) > 0:
			self.current_graph.set_data( *zip(*self.current_graph_data) )

		if self.newest_data is not None:
			self.running_graph.set_data( [self.newest_data[0]], [self.newest_data[1]] )
		#self.current_graph.set_data( [1,2], [1,2] )
		#print( self.current_graph_data )
		# refresh canvas
		self.ax.relim()
		#self.ax.autoscale_view()
		#self.ax.autoscale(enable=True, axis='y')
		self.ax.autoscale_view(True,True,True)
		self.figure.tight_layout()
		#plt.pause(0.05)
		#self.canvas.draw()
		#self.canvas.show()
		return self.all_graphs + [self.running_graph]

	def add_new_data_point( self, x, y ):
		self.newest_data = (x,y)
		self.current_graph_data.append( (x, y) )

	def plot_finished( self, x_data, y_data ):
		self.ani._stop()
		self.running_graph.remove()
		self.current_graph.set_data( *zip(*self.current_graph_data) )
		self.ax.relim()
		#self.ax.autoscale_view()
		self.ax.autoscale_view(True,True,True)
		self.figure.tight_layout()
		self.canvas.draw()
		self.canvas.show()

	def clear_all_plots( self ):
		for graph in self.all_graphs:
			graph.remove()
		self.all_graphs.clear()
		self.current_graph = None
		self.running_graph = None

	
