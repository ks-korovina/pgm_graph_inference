"""
Subgraph labeling algorithm:
splits a graph into k subgraphs and labels each individually.

@author: markcheu@andrew.cmu.edu
"""

from sklearn.cluster import spectral_clustering
import numpy as np
import networkx as nx
from networkx.algorithms import community as nx_community
import matplotlib.pyplot as plt
import community as com


import igraph as ig  #requires installing igraph from https://igraph.org/python/#startpy

class LabelSG:
	def __init__(self):
		pass

	# from https://github.com/taynaud/python-louvain
	def partition_graph(self,graph,algorithm,unweighted=False, verbose=False):
		adj2 = graph.W
		adj = np.copy(adj2)
		nx_g = nx.Graph() #networkx
		nx_g_unweighted = nx.Graph()


		for i in range(adj.shape[0]):
			for j in range(adj.shape[1]):
				if(adj[i,j]!=0):
					nx_g.add_weighted_edges_from([(i,j,adj[i,j])])
					nx_g_unweighted.add_edge(i,j)
		
		if(unweighted):
			nx_g = nx_g_unweighted

		# convert to Igraph to use their community detection algorithms.
		ig_g = ig.Graph(len(nx_g), list(zip(*list(zip(*nx.to_edgelist(nx_g)))[:2])))
		ig_g_unweighted = ig.Graph(len(nx_g_unweighted), list(zip(*list(zip(*nx.to_edgelist(nx_g)))[:2])))

		if(verbose):
			print('Adjacency matrix: ', adj)

		if(algorithm=='Louvain'):
			partition = com.best_partition(nx_g_unweighted,resolution=100000)
			if(verbose):
				print('Partition by Louvain Algorithm: ', partition)
				self.visualize_partition(nx_g_unweighted,partition)

		elif(algorithm=='Girvan_newman'):
			communities_generator = nx_community.girvan_newman(nx_g)
			top_level_communities = next(communities_generator)
			next_level_communities = next(communities_generator)
			partition_unorganized = sorted(map(sorted, next_level_communities))
			partition = self.partition_to_dict(nx_g,partition_unorganized)
			if(verbose):
				print('Partition by Girvan-Newman Algorithm: ', partition)

		# for other choices, see https://igraph.org/python/doc/python-igraph.pdf, https://yoyoinwanderland.github.io/2017/08/08/Community-Detection-in-Python/
		elif(algorithm=='igraph-community_infomap'):
			community = ig_g.community_infomap()
			partition = self.partition_to_dict2(nx_g,community)
			if(verbose):
				print('Partition by community infomap ', partition)

		elif(algorithm=='igraph-label_propagation'):			
			community = ig_g.community_label_propagation()
			partition = self.partition_to_dict2(nx_g,community)
			if(verbose):
				print('Partition by label propagation ', partition)

		elif(algorithm=='igraph-optimal_modularity'):
			if(nx_g.number_of_nodes()>50):
				print('Too many nodes')
				return
			community = ig_g.community_optimal_modularity() #for small graph
			partition = self.partition_to_dict2(nx_g,community)
			if(verbose):
				print('Partition by integer programming (optimal modularity)', partition)


		elif(algorithm=='test'):
			print('GSP approach')

		else:
			raise NotImplementedError("Partition {} not implemented yet.".format(algorithm))

		return partition

	# Visualize Partition
	def visualize_partition(self, graph, partition):
		size = float(len(set(partition.values())))
		pos = nx.spring_layout(graph)
		count = 0.
		for com in set(partition.values()) :
		    count = count + 1.
		    list_nodes = [nodes for nodes in partition.keys()
		                                if partition[nodes] == com]
		    nx.draw_networkx_nodes(graph, pos, list_nodes, node_size = 20,
		                                node_color = str(count / size))

		nx.draw_networkx_edges(graph, pos, alpha=0.5)
		plt.show()

	# Visualize Adjacency Matrix
	def plot_adj(self, adj):
		plt.imshow(adj, interpolation='none')
		plt.colorbar()
		plt.show()

	# Convert Partition to Dictionary format (from network community): node id: partiiton 
	def partition_to_dict(self, graph,partition_unorganized):
		count = 0
		partition = {}
		for i in range(len(partition_unorganized)):
			partition_i = partition_unorganized[i]
			for j in range(len(partition_i)):
				partition[partition_i[j]]=count
			count += 1
		return partition

	# Convert Partition to Dictionary format (from igraph): node id: partiiton 
	def partition_to_dict2(self, graph,partition_unorganized):
		count = 0
		partition = {}
		for i in range(len(partition_unorganized)):
			partition_i = partition_unorganized[i]
			for j in range(len(partition_i)):
				partition[partition_i[j]]=count
			count += 1
		return partition