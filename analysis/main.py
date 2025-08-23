import networkx as nx
import json
from collections import defaultdict

from utils import (
    load_unweighted_graph,
    load_weighted_graph,
    detect_louvain_communities,
    detect_leiden_communities,
    girvan_newman_best_partition,
    calculate_number_of_communities,
    calculate_community_sizes,
    calculate_modularity,
    calculate_modularity_density,
    calculate_conductance,
    visualize_communities,
    visualize_communities_based_on_hash,
    calculate_partition_similarity,
    label_propagation_communities,
)


def main():
    # Load graphs
    unweighted_graph = load_unweighted_graph(
        "edgelist_content.txt"
    )
    weighted_graph = load_weighted_graph(
        "edgelist_content_weighted.txt"
    )

    # unweighted_graph = nx.karate_club_graph()
    # weighted_graph = unweighted_graph.copy()
    # for u, v in unweighted_graph.edges():
    #     common_neighbors = list(nx.common_neighbors(unweighted_graph, u, v))
    #     weighted_graph[u][v]["weight"] = len(common_neighbors)

    # Define community detection algorithms
    algorithms = {
        "Louvain": detect_louvain_communities,
        "Leiden": detect_leiden_communities,
    }

    weighted_partitions = {}
    unweighted_partitions = {}


    # Loop through each algorithm
    for algo_name, algo_func in algorithms.items():
        print(f"\n===== {algo_name} Algorithm =====")

        # Detect communities for unweighted graph
        if algo_name == "Girvan-Newman":
            unweighted_partition, unweighted_modularity = algo_func(unweighted_graph, max_splits=2)
            weighted_partition, weighted_modularity = algo_func(weighted_graph, max_splits=2)
        else:
            unweighted_partition = algo_func(unweighted_graph, is_weighted=False)
            weighted_partition = algo_func(weighted_graph, is_weighted=True)
            unweighted_modularity = calculate_modularity(
                unweighted_graph, unweighted_partition
            )
            weighted_modularity = calculate_modularity(
                weighted_graph, weighted_partition
            )

        # Unweighted graph metrics
        print("\n-- Unweighted Graph --")
        num_communities_unweighted = calculate_number_of_communities(
            unweighted_partition
        )
        sizes_unweighted = calculate_community_sizes(unweighted_partition)

        unweighted_mod_density = calculate_modularity_density(
            unweighted_graph, unweighted_partition
        )
        unweighted_conductance = calculate_conductance(
            unweighted_graph, unweighted_partition
        )

        print(f"Number of communities: {num_communities_unweighted}")
        print(f"Community sizes: {sizes_unweighted}")
        print(f"Modularity: {unweighted_modularity}")
        print(f"Modularity Density: {unweighted_mod_density}")
        print(f"Conductance: {unweighted_conductance}")

        # Visualize unweighted graph communities
        visualize_communities_based_on_hash(
            unweighted_graph,
            unweighted_partition,
            f"{algo_name} Communities in Unweighted Graph",
            f"{algo_name}_unweighted_graph.png"
        )

        # Weighted graph metrics
        print("\n-- Weighted Graph --")
        num_communities_weighted = calculate_number_of_communities(weighted_partition)
        sizes_weighted = calculate_community_sizes(weighted_partition)
        weighted_mod_density = calculate_modularity_density(
            weighted_graph, weighted_partition
        )
        weighted_conductance = calculate_conductance(weighted_graph, weighted_partition)

        print(f"Number of communities: {num_communities_weighted}")
        print(f"Community sizes: {sizes_weighted}")
        print(f"Modularity: {weighted_modularity}")
        print(f"Modularity Density: {weighted_mod_density}")
        print(f"Conductance: {weighted_conductance}")


        # Compare partitions (Louvain vs Leiden or other algorithms)
        ari, nmi = calculate_partition_similarity(
            unweighted_partition, weighted_partition
        )
        print("\n-- The partitions Similarity amount: --")
        print(f"Adjusted Rand Index (ARI): {ari}")
        print(f"Normalized Mutual Information (NMI): {nmi}")

        weighted_partitions[algo_name] = weighted_partition
        unweighted_partitions[algo_name] = unweighted_partition


        # Visualize weighted graph communities
        visualize_communities_based_on_hash(
            weighted_graph,
            weighted_partition,
            f"{algo_name} Communities in Weighted Graph",
            f"{algo_name}_weighted_graph.png"

        )

    print("\n-- The unweighted communities similarity from two algos --")

    partition_values = list(weighted_partitions.values())
    partition_names = list(weighted_partitions.keys())

    for i in range(len(partition_values)):
        for j in range(i + 1, len(partition_values)):
            ari, nmi = calculate_partition_similarity(partition_values[i], partition_values[j])
            print(f"Comparison {partition_names[i]} vs {partition_names[j]}: ARI={ari}, NMI={nmi}")
    # Compare partitions (Louvain vs Leiden or other algorithms)
    # ari, nmi = calculate_partition_similarity(
    #     weighted_partitions[0], weighted_partitions[1]
    # )
    # print("\n-- The partitions Similarity amount: --")
    # print(f"Adjusted Rand Index (ARI): {ari}")
    # print(f"Normalized Mutual Information (NMI): {nmi}")    

    community_dict = {}

    # Process unweighted partitions
    for algo_name, partition in unweighted_partitions.items():
        community_groups = defaultdict(list)  # Using defaultdict to collect instances by community label
        for instance, community_label in partition.items():
            community_groups[community_label].append(instance)

        # Save each community as a list of instances
        for community_label, instances in community_groups.items():
            key = f"{algo_name.lower()}_unweighted_community_{community_label}"
            community_dict[key] = instances

    # Process weighted partitions
    for algo_name, partition in weighted_partitions.items():
        community_groups = defaultdict(list)  # Using defaultdict to collect instances by community label
        for instance, community_label in partition.items():
            community_groups[community_label].append(instance)

        # Save each community as a list of instances
        for community_label, instances in community_groups.items():
            key = f"{algo_name.lower()}_weighted_community_{community_label}"
            community_dict[key] = instances

    # # Write the collected community data to the JSON file
    # with open("communities.json", "w") as f:
    #     json.dump(community_dict, f, indent=4)


if __name__ == "__main__":
    main()
