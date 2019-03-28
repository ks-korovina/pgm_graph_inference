"""

Approximate inference using Belief Propagation
Here we can rely on some existing library,
for example https://github.com/mbforbes/py-factorgraph
Authors: kkorovin@cs.cmu.edu
         lingxiao@cmu.edu
"""

from inference.core import Inference
import numpy as np 
from scipy.misc import logsumexp


class BeliefPropagation(Inference):
    """
    A special case implementation of BP
    for binary MRFs.
    Exact BP in tree structure only need two passes,
    LBP need multiple passes until convergene. 
    """

    def _safe_norm_exp(self, logit):
        logit -= np.max(logit, axis=1, keepdims=True)
        prob = np.exp(logit)
        prob /= prob.sum(axis=1, keepdims=True)
        return prob 

    def _safe_divide(self, a, b):
        '''
        Divies a by b, then turns nans and infs into 0, so all division by 0
        becomes 0.
        '''
        c = a / b
        c[c == np.inf] = 0.0
        c = np.nan_to_num(c)
        return c

    def run_one(self, graph, use_log=True, smooth=0):
        # Asynchronous BP  
        # Sketch of algorithm:
        # -------------------
        # preprocessing:
        # - sort nodes by number of edges
        # Algo:
        # - initialize messages to 1
        # - until convergence or max iters reached:
        #     - for each node in sorted list (fewest edges to most):
        #         - compute outgoing messages to neighbors
        #         - check convergence of messages

        if self.mode == "marginal": # not using log
            sumOp = logsumexp if use_log else np.sum
        else:
            sumOp = np.max
        # storage, W should be symmetric 
        max_iters = 100
        epsilon = 1e-10 # determines when to stop

        row, col = np.where(graph.W)
        n_V, n_E = len(graph.b), len(row)
        # create index dict
        degrees = np.sum(graph.W != 0, axis=0)
        index_bases = np.zeros(n_V, dtype=np.int64)
        for i in range(1, n_V): 
            index_bases[i] = index_bases[i-1] + degrees[i-1]

        neighbors = {i:[] for i in range(n_V)}
        for i,j in zip(row,col): neighbors[i].append(j)
        neighbors = {k: sorted(v) for k, v in neighbors.items()}
        # sort nodes by neighbor size 
        ordered_nodes = np.argsort(degrees)

        # init messages based on graph structure (E, 2)
        # messages are ordered (out messages)
        messages = np.ones([n_E, 2])/2
        if use_log:
            messages = np.log(messages)  # log
 
        xij = np.array([[1,-1],[-1,1]])
        xi = np.array([-1, 1])
        for _ in range(max_iters):
            converged = True
            # save old message for checking convergence
            old_messages = messages.copy()
            # update messages 
            for i in ordered_nodes:
                neighbor = neighbors[i]
                Jij = graph.W[i][neighbor] # vector 
                bi = graph.b[i]            # scalar
                local_potential = Jij.reshape(-1,1,1)*xij + bi*xi.reshape(-1,1)
                if not use_log:
                    local_potential = np.exp(local_potential)
                # get in messages product (log)
                in_message_prod = 0 if use_log else 1
                for j in neighbor:
                    if use_log:
                        in_message_prod += messages[index_bases[j]+neighbors[j].index(i)]
                    else:
                        in_message_prod *= messages[index_bases[j]+neighbors[j].index(i)]

                for k in range(degrees[i]):
                    j = neighbor[k]
                    if use_log:
                        messages[index_bases[i]+k] = in_message_prod - \
                           (messages[index_bases[j]+neighbors[j].index(i)])
                    else:
                        messages[index_bases[i]+k] = self._safe_divide(in_message_prod, 
                           messages[index_bases[j]+neighbors[j].index(i)])                        
                # update
                messages[index_bases[i]:index_bases[i]+degrees[i]] = sumOp(messages[index_bases[i]:index_bases[i]+degrees[i]].reshape(degrees[i],2,1) + local_potential, axis=1)

            # check convergence 
            if use_log:
                error = (self._safe_norm_exp(messages) - self._safe_norm_exp(old_messages))**2
            else:
                error = (messages - old_messages)**2
            error = error.mean()
            if self.verbose: print(error)
            if error < epsilon: break

        if self.verbose: print("Is BP converged: {}".format(converged))

        # calculate marginal or map
        probs = np.zeros([n_V, 2])
        for i in range(n_V):
            probs[i] = graph.b[i]*xi
            if not use_log:
                probs[i] = np.exp(probs[i])
            for j in neighbors[i]:
                if use_log:
                    probs[i] += messages[index_bases[j]+neighbors[j].index(i)] 
                else:
                    probs[i] *= messages[index_bases[j]+neighbors[j].index(i)] 

        # normalize
        if self.mode == 'marginal':
            if use_log:
                results = self._safe_norm_exp(probs)
            else:
                results = self._safe_divide(probs, probs.sum(axis=1, keepdims=True))


        if self.mode == 'map':
            results = np.argmax(probs, axis=1)
            results[results==0] = -1

        return results


    def run(self, graphs, use_log=True, verbose=False):
        self.verbose = verbose
        res = []
        for graph in graphs:
            res.append(self.run_one(graph, use_log=use_log))
        return res


if __name__ == "__main__":
    bp = BeliefPropagation("marginal")
    
