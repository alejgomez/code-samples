
# Intended to work with the PacMan AI projects from:
#
# http://ai.berkeley.edu/
#
# These use a simple API that allow us to control Pacman's interaction with
# the environment adding a layer on top of the AI Berkeley code.
#
# As required by the licensing agreement for the PacMan AI we have:
#
# Licensing Information:  You are free to use or extend these projects for
# educational purposes provided that (1) you do not distribute or publish
# solutions, (2) you retain this notice, and (3) you provide clear
# attribution to UC Berkeley, including a link to http://ai.berkeley.edu.
# 
# Attribution Information: The Pacman AI projects were developed at UC Berkeley.
# The core projects and autograders were primarily created by John DeNero
# (denero@cs.berkeley.edu) and Dan Klein (klein@cs.berkeley.edu).
# Student side autograding was added by Brad Miller, Nick Hay, and
# Pieter Abbeel (pabbeel@cs.berkeley.edu).

# Alejandro Gomez


from pacman import Directions
from game import Agent
import api
import random
import game
import util
from time import sleep , time


class MDPAgent(Agent):
    def __init__(self):
         # define if pacman has a map of the place or not
         self.hasMap = False
         # dictionary map of the whole game paths, built with BFS algo
         self.mapGraph = {}
         # utilities dictionary for each state in the walkable map
         self.utilities = {} # dictionary that gets updated by value iteration
         # pacman position
         self.position = []  
         # directions pacman can make at anytime (legal or not)
         self.possibleDirections = [Directions.WEST, Directions.NORTH,
                                     Directions.EAST, Directions.SOUTH]
         
         self.wallList = [] # wall list
         self.food = [] # food location
         self.capsules = [] # capsule location
         self.ghosts = [] # ghosts location
         self.dangerousZone = {} # dictionary takes ghost location as key; value is the path of x steps from pacman towards a ghost
         self.ghostsState = {} #dictionary about the ghost state
         self.rewardForNodeType = {  'costOfMove': -0.1, 
                                     'nodeWithGhost': -5, 
                                     'nodeWithScaredGhost': 100,
                                     'nodeWithCapsule': 2,
                                     'nodeWithFood': 1,
                                     'nodeWithoutFood': 0
                    }
         self.minScaredGhostTimer = 15  # if timer is higher than this, the ghost is edible    

    def final(self,state):
        # reinitialize variables. Used in multiple continuous runs of the program
        self.__init__()
   
    def getAction(self, state):
        # Generate candidate actions
        legal = state.getLegalPacmanActions()
        if Directions.STOP in legal: legal.remove(Directions.STOP)
        
        # get pacman location
        self.position = api.whereAmI(state)
        # get walls
        self.wallList = api.walls(state)
        # get food, capsules, ghosts
        self.food = api.food(state)
        self.capsules = api.capsules(state)
        self.ghosts =  self.getFormattedGhostsLocation(state) # converts api.ghosts(state) values into integer coords
        
        # empty the ghosts state array
        self.ghostsState = {}
        # get the state of the ghosts
        for item in api.ghostStatesWithTimes(state):
            positionX = int(item[0][0])
            positionY = int(item[0][1])
            # create a dictionary 
            # key is the ghost location as integer, value is the state timer
            self.ghostsState[(positionX, positionY)]=item[1]

        # create map of the place the first run only
        if not self.hasMap:
            self.bfs_buildMap()

        # identify the dangerous zone
        self.dangerousZone = self.getDangerousZone(self.position)
        
        # Initialize the utilities of all states 
        self.initializeUtilities()

        # Do MDP Value Iteration: At each step the utilities are updated 
        # based on MDP before making a move
        self.MDPValueIteration()
        
        # Return a move that maximises expected utility
        nextMove = self.getMEUMove(self.position, legal)
   
        return api.makeMove(nextMove, legal)

        
    # This function is called once in each game to build a map of the world
    def bfs_buildMap(self):
        # this is a bfs algorithm that builds a graph dictionary which represents all
        # positions and their children. It does so by expanding nodes in a breath first search way
        # starting from the initial position of pacman at the game start

        # we will create the map, so pacman now has map
        self.hasMap = True
        # initialize expanded nodes to empty
        expandedNodes = []
        # queue of nodes to check
        queue = [self.position] # starts with the starting position
        
        while not len(queue) == 0:
            # select first node of the queue
            node = queue.pop(0) 
            
            # if node hasnt been expanded, mark it as expanded
            if node not in expandedNodes: 
                # add node
                expandedNodes.append(node)
                
                # explore which neighbors it has and add it to the queue
                # create a neighbor array
                neighborGraph = []
                # check all directions to find neighbors
                for direction in self.possibleDirections:
                    # get position of the neighbor 
                    # without filtering out walls(3rd param is False)
                    neighbor = self.getNextPosition(node,direction,False)
                    
                    # check the neighbor is not a wall and append to neighbor graph
                    if neighbor not in self.wallList: 
                        # append the neighbor to the graph 
                        neighborGraph.append(neighbor)
                        # append neighbor to queue
                        queue.append(neighbor) 
                
                # update map graph
                self.mapGraph[node] = neighborGraph
                

    # this function returns the move that maximises Expected Utility (MEU Move)
    def getMEUMove(self, position, legal):
        # initialize maxUtility to arbirtary low value
        maxUtility = -1000
        #initialize MEU to arbitrary move
        MEUMove = Directions.STOP

        #iterate over the legal move directions
        for direction in legal:
            # calculate the expected utility of each direction
            utility = self.calculateMoveUtility(position, direction)

            # check if this utility is the new maximun utility
            if utility > maxUtility:
                maxUtility = utility
                # the MEUmove is the direction that outputs this utility
                MEUMove = direction 

        # return the max exp utility move
        return MEUMove

    # this function returns the Max Expected Utility (MEU) given a coordinate and its neighbors
    def getMEU(self, coordinate, neighbors):
        # initialize maxUtility to arbirtary value
        maxUtility = -1000

        # iterate over all neighbors (excludes walls) of a coordinate
        for neighbor in neighbors:
            # calculate the direction where the neighbor of the coordinate is
            direction = self.getNextDirection(coordinate, neighbor)
            # calculate the expected utility of moving towards that neighbor direction
            utility = self.calculateMoveUtility(coordinate, direction)
            
            # check if this utility is the new maximun utility
            if utility > maxUtility:
                maxUtility = utility

        # return the max exp utility move
        return maxUtility
                
    # This funciton calculates the expected utility of moving from current position to the 
    # specified direction based on 0.8 probability of heading to desired direction 
    # and 0.1 to each of the sides
    def calculateMoveUtility(self, position, goalDirection):
        # get intended position given the direction you want to go
        intendedPosition = self.getNextPosition(position, goalDirection)
        # get the position you'd end up if you instead turn right or left 
        # of the originally intended direction
        rightPosition = self.getNextPosition(position, Directions.RIGHT[goalDirection])
        leftPosition = self.getNextPosition(position, Directions.LEFT[goalDirection])
        
        # calculate the expected utility of this move given the non determinism 
        utility =   (0.8 * self.utilities[intendedPosition]
                   + 0.1 * self.utilities[rightPosition] 
                   + 0.1 * self.utilities[leftPosition]
        )
 
        return utility
    
    # This auxiliar function calculates the position you end up being if you are in "position" and 
    # take a move towards "goalDirection". 
    def getNextPosition(self, position, goalDirection, filterOutWalls = True):
        # define directions as key, return a position  
        choices = { 'East': ((position[0] + 1), position[1]), 
                    'West': ((position[0] - 1), position[1]),
                    'North': (position[0], (position[1] + 1)),
                    'South': (position[0], (position[1] - 1))
                    }
        
        # next position of the agent if going towards goal direction
        nextPosition = choices.get(goalDirection, "Position not found") 

        #If the boolean filterOutWalls is True, we cannot return 
        # a next position that is a wall. By default its True.
        if filterOutWalls:
            # if nextPosition is a wall its impossible Pacman will go over it,
            # return the original position
            if nextPosition in self.wallList:
                return position

        # return next position
        return nextPosition

    # This function tells the direction you have to go to 
    # in order toget to the nextNeighborPosition
    def getNextDirection(self, position, nextNeighborPosition):
        # define the directions dictionary
        choices = { ((position[0] + 1), position[1]): Directions.EAST, 
                    ((position[0] - 1), position[1]): Directions.WEST,
                    (position[0], (position[1] + 1)): Directions.NORTH,
                    (position[0], (position[1] - 1)): Directions.SOUTH
                    }
        
        # determine the direction to go to reach the neighbor 
        nextDirection = choices.get(nextNeighborPosition, "Direction not found") 
        
        #return the direction
        return nextDirection
    
    # This function formats the ghosts's location as integers for further processing 
    # since the ghosts api returns double numbers which are not useful
    def getFormattedGhostsLocation(self, state):
        ghostsLocation = []
        ghostsLocationRaw = api.ghosts(state)
        # format ghosts's location as integers for processing 
        for point in ghostsLocationRaw:
            newPointX = int(point[0])
            newPointY = int(point[1])
            newPoint = (newPointX, newPointY)
            ghostsLocation.append((newPointX,newPointY))
        
        return ghostsLocation
    
    # This function returns dictionary of dangerous positions
    # which are those coordinates 5 steps away from the ghost on a path from pacman to a ghost.
    # The dangerous zone excludes the ghosts.
    def getDangerousZone(self, position):
        # initialize the danger zone to empty dictionary
        # the key is the ghost, the values is the path to this ghost
        dangerZone = {}
        # define minimum distance to keep away from ghosts
        minimumDistanceToGhost = 5  # given in steps
       
        # iterate over the ghosts to determine distance from pacman
        for ghost in self.ghosts:
            # calculate shortest path from pacman to the ghost
            pathToGhost = self.shortestPath(self.mapGraph, position, ghost)
            # check if distance is less than minimum allowed proximity to the ghost
            while len(pathToGhost) > minimumDistanceToGhost: 
                # for every node in this dangerous path to the ghost add it to danger zone
                pathToGhost.pop(0)

            # fill up the dictionary of dangerous positions
            for node in pathToGhost:
                if node not in dangerZone and node not in self.ghosts:
                    dangerZone[node] = ghost 
                
        # return the danger zone 
        return dangerZone

    # This function initializes the global dictionary of state utilities 
    def initializeUtilities(self):
        
        # initialize all utilities
        for node in self.mapGraph.keys():
            # utilities for nodes with ghost 
            if node in self.ghosts:
                # check if the ghost is scared.
                if self.ghostsState[node] > self.minScaredGhostTimer:
                    # ghost is scared we can try to eat it
                    self.utilities[node] = self.rewardForNodeType.get("nodeWithScaredGhost")
                else:
                    # ghost is not edible or its too dangerous to get nearby
                    self.utilities[node] = self.rewardForNodeType.get("nodeWithGhost")
            elif node in self.dangerousZone.keys():
                # find out to which ghost the dangerous zone refers to
                ghost = self.dangerousZone.get(node)
                if self.ghostsState[ghost] > 15:
                    # ghost is scared we can try to eat it
                    self.utilities[node] = self.rewardForNodeType.get("nodeWithScaredGhost")
                else:
                    # ghost is not edible or its too dangerous to get nearby
                    self.utilities[node] = self.rewardForNodeType.get("nodeWithGhost")
            elif node in self.food:
                self.utilities[node] = self.rewardForNodeType.get("nodeWithFood")
            elif node in self.capsules:
                self.utilities[node] = self.rewardForNodeType.get("nodeWithCapsule")  
            else: 
                # the node has no food, thus reward is 0
                self.utilities[node] = self.rewardForNodeType.get("nodeWithoutFood")

    # This function R(s) returns the reward for a state s. Used in the Bellman update
    def rewardForState(self, coordinate):
        # never called for states with ghosts
        reward = self.rewardForNodeType.get("costOfMove")
        
        # rewards for nodes in dangerous zone
        if coordinate in self.dangerousZone.keys():
                # find out to which ghost the dangerous zone refers to
                ghost = self.dangerousZone.get(coordinate)
                if self.ghostsState[ghost] > self.minScaredGhostTimer:
                    # ghost is scared, positive rewards
                    reward = self.rewardForNodeType.get("nodeWithScaredGhost")
                else:
                    # ghost is not edible, negative reward
                    reward = self.rewardForNodeType.get("nodeWithGhost")    
        elif coordinate in self.food: # rewards for food
            reward = self.rewardForNodeType.get("nodeWithFood")
           
        elif coordinate in self.capsules: # rewards for capsules
            reward = self.rewardForNodeType.get("nodeWithCapsule")
            

        return reward

    # This function runs an MDP value iteration update algorithm.
    def MDPValueIteration(self): 
        # Parameters for the Bellman Update 
        maxConvergenceError = 0.08 # set the maximun allowed error in the convergence tests
        maxUtilityChange = 0 # initialize the maximun utility change as zero
        discountFactor  = 0.78 #factor r in the Bellman equation

        # repeat the Bellman update until convergence test passes (breaks)
        while True:
            newUtilities = {}
            maxUtilityChange = 0 

            # One bellman update iteration over all states (coordinates)
            for coordinate, neighbors in self.mapGraph.items():

                # ghosts are terminal states, they dont get updated
                # update the utilities with the bellman Update for the rest of states
                if coordinate not in self.ghosts:
                    newUtilities[coordinate] = self.rewardForState(coordinate) + (discountFactor * self.getMEU(coordinate, neighbors))
                else:
                    # terminal states keep the same utility always
                    newUtilities[coordinate] = self.utilities[coordinate]

                # calculate the maximum difference in utility between old utility table
                #  and the new one |U'|s| - U|s||
                utilityChange = abs(newUtilities[coordinate] - self.utilities[coordinate])
            
                # calculating if this utility change is the current maximun for this Bellman iteration
                if utilityChange > maxUtilityChange:
                    # new maximum utiliy change was found
                    maxUtilityChange = utilityChange

            # =======In between Bellman update iterations:======

            # The new utilities become the default utilities U <- U'
            self.utilities = newUtilities

            # Check if the utilities pass the convergence test 
            # (termination condition of the value iteration algorithm)
            # The value iteration stops when the maxUtilityChange becomes insignificant.
            if maxUtilityChange < maxConvergenceError * ((1-discountFactor)/discountFactor):
                break

            
    # This function returns a shortest path from a certain position to a certain goal by BFS
    # Used by pacman to determine the path to a ghost, and judge whether its dangerous or not 
    # and update its utilities accordingly
    def shortestPath(self, mapGraph, position, goal):
        # initialize expanded nodes to empty
        explored = []
        queue = [[position]] # starts with the starting position
        
        # evaluate each node from the queue as long as its not empty
        while not len(queue) == 0:
            # path
            path = queue.pop(0) 
            #last node from the path
            node = path[-1]
            
            if node not in explored: 
                # get the neighbor of this node from the graph
                neighbors = mapGraph[node]
                # for aeach of this neighbors
                for neighbor in neighbors:
                    shortestPath = list(path)
                    shortestPath.append(neighbor)
                    
                    # append path to queue
                    queue.append(shortestPath) 
                    # if the node being examined is the goal node, then return the path
                    if neighbor == goal:
                        # eliminate the very first item from the path because it is the starting position
                        shortestPath.pop(0)
                        # return the final path
                        return shortestPath

                # if node hasnt been visited, mark it explored  
                explored.append(node)
        

        










        


