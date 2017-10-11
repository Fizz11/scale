"""Defines the class for handling recipe nodes"""
from __future__ import unicode_literals

from job.data.job_data import JobData


class RecipeNode(object):
    """Represents a node in a recipe
    """

    def __init__(self, job_name, job_type_name, job_type_version):
        """Constructor

        :param job_name: The unique name of the node's job
        :type job_name: str
        :param job_type_name: The name of the node's job type
        :type job_type_name: str
        :param job_type_version: The version of the node's job type
        :type job_type_version: str
        """

        self.job_name = job_name
        self.job_type_name = job_type_name
        self.job_type_version = job_type_version
        self.parents = []
        self.children = []
        self.inputs = {}  # {Input name: NodeInputConnection}

    def add_child(self, child_node):
        """Adds a child node that is dependent on this node

        :param child_node: The child node to add
        :type child_node: :class:`recipe.handlers.node.RecipeNode`
        """

        self.children.append(child_node)

    def add_dependency(self, parent_node, connections):
        """Adds a parent node upon which this node is dependent

        :param parent_node: The parent node to add
        :type parent_node: :class:`recipe.handlers.node.RecipeNode`
        :param connections: The connections to the parent's outputs
        :type connections: [:class:`recipe.handlers.connection.DependencyInputConnection`]
        """

        self.parents.append(parent_node)
        for connection in connections:
            self.inputs[connection.input_name] = connection

    def add_recipe_input(self, recipe_input):
        """Adds a recipe input connection to this node

        :param recipe_input: The recipe input connection
        :type recipe_input: :class:`recipe.handlers.connection.RecipeInputConnection`
        """

        self.inputs[recipe_input.input_name] = recipe_input

    def create_job_data(self, job_interface, recipe_data, parent_results):
        """Creates the data for the job within this node. The parent_results must contain completed results from every
        parent node that this node depends upon.

        :param job_interface: The job's interface
        :type job_interface: :class:`job.configuration.interface.job_interface.JobInterface`
        :param recipe_data: The recipe data
        :type recipe_data: :class:`recipe.configuration.data.recipe_data.RecipeData`
        :param parent_results: The results of each parent job stored by job name
        :type parent_results: {str: :class:`job.results.job_results.JobResults`}
        :returns: The created job data
        :rtype: :class:`job.data.job_data.JobData`
        """

        job_data = JobData({})

        for input_connection in self.inputs.values():
            input_connection.add_input_to_job_data(job_data, recipe_data, parent_results)

        # Add workspace for file outputs if needed
        if job_interface.get_file_output_names():
            job_interface.add_workspace_to_data(job_data, recipe_data.get_workspace_id())

        return job_data
