import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from collections import Counter
import seaborn as sns

from utils import load_unweighted_graph

def compute_centralities_and_plot_heatmap(graph):
    """
    Compute centrality measures for the given graph, extract the top 10 nodes for each measure,
    and generate a heatmap.
    
    Parameters:
        graph (networkx.Graph): Input network graph.
    
    Returns:
        pd.DataFrame: DataFrame containing top 10 nodes for each centrality measure.
    """
    # Compute centrality measures
    degree_centrality = nx.degree_centrality(graph)
    betweenness_centrality = nx.betweenness_centrality(graph)
    closeness_centrality = nx.closeness_centrality(graph)
    eigenvector_centrality = nx.eigenvector_centrality(graph, max_iter=1000)
    pagerank_centrality = nx.pagerank(graph)
    hits_hubs, hits_authorities = nx.hits(graph, max_iter=1000)

    # Store centrality measures in a dictionary
    centralities = {
        "Degree": degree_centrality,
        "Betweenness": betweenness_centrality,
        "Closeness": closeness_centrality,
        "Eigenvector": eigenvector_centrality,
        "PageRank": pagerank_centrality,
        "HITS Hubs": hits_hubs,
        "HITS Authorities": hits_authorities
    }

    # Extract top 10 nodes for each centrality measure
    top_nodes = {
        measure: sorted(values.items(), key=lambda x: x[1], reverse=True)[:10]
        for measure, values in centralities.items()
    }

    # Create DataFrame for visualization
    df_top = pd.DataFrame({
        measure: {node: score for node, score in nodes}
        for measure, nodes in top_nodes.items()
    }).fillna(0)  # Fill NaNs with 0 if some nodes appear only in some measures

    # Plot heatmap
    plt.figure(figsize=(10, 10))
    sns.heatmap(df_top, cmap="coolwarm", annot=True, fmt=".4f", linewidths=0.5)
    plt.title("Top 10 Nodes by Centrality Measures")
    plt.xlabel("Centrality Measure")
    plt.ylabel("Node")
    plt.xticks(rotation=45)
    plt.yticks(rotation=0)

    # Save plot
    plt.savefig("visualizations/centrality_heatmap.png", dpi=300, bbox_inches='tight')
    plt.close()

    return df_top



unweighted_graph = load_unweighted_graph(
    "edgelist_content.txt"
)

df_centrality = compute_centralities_and_plot_heatmap(unweighted_graph)

print(df_centrality)