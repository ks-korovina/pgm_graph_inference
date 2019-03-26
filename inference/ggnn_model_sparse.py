"""
Defines GGNN model based on the PGM by GNN workshop paper.
Authors: kkorovin@cs.cmu.edu, markcheu@andrew.cmu.edu, lingxiao@cmu.edu
"""

import torch
import torch.nn as nn

class SpecialSpmmFunction(torch.autograd.Function):
    """Special function for only sparse region backpropataion layer."""
    @staticmethod
    def forward(ctx, indices, values, shape, b):
        assert indices.requires_grad == False
        a = torch.sparse_coo_tensor(indices, values, shape)
        ctx.save_for_backward(a, b)
        ctx.N = shape[0]
        return torch.matmul(a, b)

    @staticmethod
    def backward(ctx, grad_output):
        a, b = ctx.saved_tensors
        grad_values = grad_b = None
        if ctx.needs_input_grad[1]:
            grad_a_dense = grad_output.matmul(b.t())
            edge_idx = a._indices()[0, :] * ctx.N + a._indices()[1, :]
            grad_values = grad_a_dense.view(-1)[edge_idx]
        if ctx.needs_input_grad[3]:
            grad_b = a.t().matmul(grad_output)
        return None, grad_values, None, grad_b

class SpecialSpmm(nn.Module):
    def forward(self, indices, values, shape, b):
        return SpecialSpmmFunction.apply(indices, values, shape, b)

class Special3dSpmm(nn.Module):
    # sparse matrix a is (n_dim0, n_dim1, n_dim2)
    # full matrix b is (n_dim2, n_dim3)
    # perform a.matmul(b), output shape is (n_dim1, n_dim3, n_dim0)
    # if n_dim3 ==1, output shape is (n_dim1, n_dim0)
    def forward(self, indices, values, shape, b):
        idx0, idx1, idx2 = indices 
        n_dim0, n_dim1, n_dim2 = shape
        out = []
        for i in range(n_dim0):
            idx = (idx0 == i)
            new_indices = torch.cat([idx1[idx].unsqueeze(0), idx2[idx].unsqueeze(0)], dim=0)
            out.append(SpecialSpmmFunction.apply(new_indices, values[idx], shape[1:], b))
        return torch.cat(out, dim=-1) # (n_dim1, n_dim0)


class GGNN(nn.Module):
    def __init__(self, n_nodes, state_dim, message_dim,hidden_unit_message_dim, hidden_unit_readout_dim, n_steps=10):
        super(GGNN, self).__init__()

        self.state_dim = state_dim
        self.n_nodes = n_nodes
        self.n_steps = n_steps
        self.message_dim = message_dim
        self.hidden_unit_message_dim = hidden_unit_message_dim
        self.hidden_unit_readout_dim = hidden_unit_readout_dim

        self.propagator = nn.GRUCell(self.message_dim, self.state_dim)
        self.message_passing = nn.Sequential(
            nn.Linear(2*self.state_dim+1+2, self.hidden_unit_message_dim),
            # 2 for each hidden state, 1 for J[i,j], 1 for b[i] and 1 for b[j]
            nn.ReLU(),
            nn.Linear(self.hidden_unit_message_dim, self.hidden_unit_message_dim),
            nn.ReLU(),
            nn.Linear(self.hidden_unit_message_dim, self.message_dim),
        )
        self.readout = nn.Sequential(
            nn.Linear(self.state_dim, self.hidden_unit_readout_dim),
            nn.ReLU(),
            nn.Linear(self.hidden_unit_readout_dim, self.hidden_unit_readout_dim),
            nn.ReLU(),
            nn.Linear(self.hidden_unit_readout_dim, 2),
        )
        
        self.sigmoid = nn.Sigmoid()
        self.spmm = Special3dSpmm()
        self._initialization()


    def _initialization(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                m.weight.data.normal_(0, 0.1)
                m.bias.data.fill_(0)

    # unbatch version for debugging
    def forward(self, J, b):
        readout = torch.zeros(self.n_nodes)
        hidden_states = torch.zeros(self.n_nodes, self.state_dim).to(J.device)
        # TODO: change to sparse matrix
        row, col = torch.nonzero(J).t()
        edges = torch.nonzero(J.unsqueeze(-1).expand(-1, -1, self.message_dim).permute(2,0,1)).t()# (dim2*dim0*dim1) 
        # print(torch.nonzero(J).t())
        # print(edges)
        
        for step in range(self.n_steps):
            # (dim0*dim1, dim2)
            edge_messages = torch.cat([hidden_states[row,:], hidden_states[col,:],J[row,col].unsqueeze(-1),b[row].unsqueeze(-1),b[col].unsqueeze(-1)], dim=-1)
            edge_messages = self.message_passing(edge_messages).t().reshape(-1) # in message, (dim2*dim0*dim1)
            node_messages = self.spmm(edges, edge_messages, torch.Size([self.message_dim, self.n_nodes, self.n_nodes]), 
                                      torch.ones(size=(self.n_nodes,1)).cuda()) # (dim0, dim2)
            hidden_states = self.propagator(node_messages, hidden_states) 

        readout = self.readout(hidden_states)
        readout = self.sigmoid(readout)
        readout = readout / torch.sum(readout,1).view(-1,1)
        return readout
