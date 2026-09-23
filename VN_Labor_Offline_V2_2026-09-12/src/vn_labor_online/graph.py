from __future__ import annotations
import heapq,re,time
from collections import defaultdict
from .artifact_store import ArtifactStore
from .config import GraphConfig
from .models import Evidence
from .retrieval import as_evidence,authority_score

GAP_RELATIONS={
  'applicable_version':{'AMENDS','REPEALS','REPLACES','VERSION_OF'},
  'mandatory_reference':{'REFERENCES','IMPLEMENTS'},
  'implementing_regulation':{'IMPLEMENTS','REFERENCES'},
  'amendment_history':{'AMENDS','REPEALS','REPLACES','VERSION_OF'},
  'exceptions':{'REFERENCES','PART_OF','NEXT'},
  'conditions':{'REFERENCES','PART_OF','NEXT'},
  'termination_conditions':{'REFERENCES','PART_OF','NEXT','RELATES_TO_ISSUE'},
  'notice_requirement':{'REFERENCES','PART_OF','NEXT','RELATES_TO_ISSUE'},
  'case_law':{'CITES','HAS_ISSUE','RELATES_TO_ISSUE','SIMILAR_TO'},
  'official_source':{'VERSION_OF','PART_OF'},
}

class GraphExplorer:
    def __init__(self,store:ArtifactStore,cfg:GraphConfig):
        self.store=store; self.cfg=cfg; self.adj=defaultdict(list); self.degree=defaultdict(int)
        for edge in store.edges:
            self.adj[edge['source']].append((edge,edge['target'])); self.adj[edge['target']].append((edge,edge['source']))
            self.degree[edge['source']]+=1; self.degree[edge['target']]+=1
        self.max_degree=max(self.degree.values(),default=1)
    def expand_round(self,frontier_ids:list[str],gaps:list[str],query:str,visited:set[str],paths:dict[str,list[str]],remaining_nodes:int,remaining_edges:int):
        started=time.monotonic(); queue=[]; serial=0
        preferred=set().union(*(GAP_RELATIONS.get(gap,set()) for gap in gaps))
        for source in frontier_ids:
            for edge,target in self.adj.get(source,[]):
                if target in visited: continue
                if preferred and edge['type'] not in preferred: continue
                score,parts=self._score(edge,target,gaps,query,source)
                heapq.heappush(queue,(-score,serial,target,source,edge,parts)); serial+=1
        added=[]; new_frontier=[]; edge_count=0; followed=[]
        while queue and len(new_frontier)<remaining_nodes and edge_count<remaining_edges:
            if (time.monotonic()-started)*1000>self.cfg.wall_clock_ms: break
            neg,_,node_id,parent,edge,parts=heapq.heappop(queue); edge_count+=1
            if node_id in visited: continue
            visited.add(node_id); new_frontier.append(node_id)
            if edge['type'] in preferred: followed.append(edge['type'])
            paths[node_id]=paths.get(parent,[])+[edge['id']]
            unit=self.store.units_by_id.get(node_id)
            if unit:
                added.append(as_evidence(unit,max(0,-neg),'graph',len(added)+1,parts).model_copy(update={'graph_path':paths[node_id]}))
        return added,new_frontier,{'nodes_added':len(new_frontier),'edges_visited':edge_count,
          'critical_edges_followed':list(dict.fromkeys(followed)),'elapsed_ms':round((time.monotonic()-started)*1000,2)}
    def expand(self,seeds:list[Evidence],gaps:list[str],query:str='')->tuple[list[Evidence],dict]:
        """Compatibility wrapper that performs bounded multi-round expansion."""
        visited={e.unit_id for e in seeds}; paths={e.unit_id:list(e.graph_path) for e in seeds}; frontier=list(visited)
        all_added=[]; edge_count=0; rounds=0; followed=[]; started=time.monotonic()
        round_limit=min(self.cfg.max_rounds,self.cfg.max_hops)
        while frontier and rounds<round_limit and len(visited)<self.cfg.max_nodes and edge_count<self.cfg.max_edges:
            added,frontier,stats=self.expand_round(frontier,gaps,query,visited,paths,self.cfg.max_nodes-len(visited),self.cfg.max_edges-edge_count)
            all_added.extend(added); edge_count+=stats['edges_visited']; followed+=stats['critical_edges_followed']; rounds+=1
            if not frontier: break
        return all_added,{'nodes_visited':len(visited),'edges_visited':edge_count,'rounds':rounds,
          'critical_edges_followed':list(dict.fromkeys(followed)),'elapsed_ms':round((time.monotonic()-started)*1000,2)}
    def _score(self,edge,target,gaps,query,parent):
        typ=edge['type']; legal=self.cfg.edge_weights.get(typ,0); target_unit=self.store.units_by_id.get(target)
        props=(self.store.nodes_by_id.get(target) or {}).get('properties') or {}
        text=(target_unit or {}).get('text') or ' '.join(str(v) for v in props.values() if isinstance(v,(str,int)))
        parent_unit=self.store.units_by_id.get(parent)
        parent_props=(self.store.nodes_by_id.get(parent) or {}).get('properties') or {}
        parent_text=(parent_unit or {}).get('text') or ' '.join(str(v) for v in parent_props.values() if isinstance(v,(str,int)))
        query_terms={x for x in re.findall(r'\w+',query.lower()) if len(x)>3}; target_terms=set(re.findall(r'\w+',text.lower()))
        parent_terms=set(re.findall(r'\w+',parent_text.lower()))
        relevance=len(query_terms&target_terms)/max(1,len(query_terms)); authority=authority_score(as_evidence(target_unit,0,'graph',0)) if target_unit else 0
        temporal=float(bool(target_unit and (target_unit.get('provision_temporal_verified') or target_unit.get('temporal_verified'))))
        preferred=set().union(*(GAP_RELATIONS.get(gap,set()) for gap in gaps)); gap=float(typ in preferred)
        union=target_terms|parent_terms
        redundancy=len(target_terms&parent_terms)/max(1,len(union))
        novelty=len(target_terms-parent_terms)/max(1,len(target_terms))
        hub=self.cfg.hub_penalty*(self.degree[target]/self.max_degree); cost=self.cfg.traversal_cost_weight
        score=(legal+self.cfg.relevance_weight*relevance+self.cfg.authority_weight*authority+
          self.cfg.temporal_weight*temporal+self.cfg.gap_weight*gap+self.cfg.novelty_weight*novelty-
          self.cfg.redundancy_weight*redundancy-hub-cost)
        return score,{'graph':score,'legal_importance':legal,'relevance':relevance,'authority':authority,
          'temporal':temporal,'gap_contribution':gap,'novelty':novelty,'redundancy':redundancy,
          'hub_penalty':hub,'traversal_cost':cost}
