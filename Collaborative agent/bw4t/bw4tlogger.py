from matrx.logger.logger import GridWorldLogger # type: ignore


class BW4TLogger(GridWorldLogger):
    '''
    Logs the things we need for bw4t:
    agent actions, world-completed info, messages info
    '''
    def __init__(self, save_path="", file_name_prefix="", file_extension=".csv", delimeter=";"):
        super().__init__(save_path=save_path, file_name=file_name_prefix, file_extension=file_extension,
                         delimiter=delimeter, log_strategy=1)

    def log(self, grid_world, agent_data):
        # So agent_data is a dictionary of shape: {<agent id>: <result from agent's get_log_data>, ...}
        # Knowing that it contains only a boolean, a number of messages, and the agent's name lets format it in some
        # nice columns
        data = {}
        # simulation goal must be our CollectionGoal
        data['done'] = grid_world.simulation_goal.isBlocksPlaced(grid_world)
        for agent_id, log_data in agent_data.items():

            nmsgs=0
            dropped=0
            if len(log_data) > 0:
                dropped = log_data["dropped_block"]
                nmsgs = log_data["prev_tick_messages"]

            data[agent_id+'_msgs'] = nmsgs
            data[agent_id+'_drops'] = dropped


        for agent_id, agent_body in grid_world.registered_agents.items():
            data[agent_id+'_acts'] = agent_body.current_action

        return data

    # workaround for issue matrx267
    def getFileName(self):
        '''
        @return the log filename written by this logger
        '''
        return self._GridWorldLogger__file_name
    