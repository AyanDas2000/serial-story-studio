"""Build an explicitly fake, separately saved memory-view fixture. No network."""
import json
from pathlib import Path
import uuid

from serial_story.cli import export_without_overwrite
from serial_story.graph import render_graph
from serial_story.repository import SQLiteRepository
from serial_story.service import StoryService


ROOT = Path(__file__).resolve().parent
folder = ROOT / 'local' / ('memory-preview-' + uuid.uuid4().hex[:12])
folder.mkdir(parents=True, exist_ok=False)
db = folder / 'fixture.db'
with SQLiteRepository(db) as repo:
    studio = StoryService(repo)
    studio.initialize('OFFLINE FIXTURE, NOT A DEMO STORY: a harbor map conceals a room.')
    studio.approve_plan(studio.propose_plan().id)
    draft = studio.draft()
    prefix = 'Ivo is alive. Ivo waits at the harbor. Mara carries the map. Mara knows Ivo is alive. The harbor road leads to the abandoned lighthouse. '
    accepted = studio.accept(draft.id, edited_text=prefix + draft.text)
    memory = studio.memory
    ivo = memory.add_entity('Ivo', 'character', 'protagonist')
    mara = memory.add_entity('Mara', 'character', 'core')
    harbor = memory.add_entity('Harbor', 'location')
    lighthouse = memory.add_entity('Lighthouse', 'location')
    scene = memory.add_situation('Waiting at the harbor', accepted.revision_id, 'Ivo waits at the harbor.')
    rows = [(ivo.id,'status','alive','Ivo is alive. Ivo waits at the harbor.',None,scene.id),
            (ivo.id,'at','Harbor','Ivo waits at the harbor.',harbor.id,scene.id),
            (mara.id,'carries','map','Mara carries the map.',None,None),
            (mara.id,'knows_ivo_alive','true','Mara knows Ivo is alive.',ivo.id,None),
            (harbor.id,'road_to','Lighthouse','The harbor road leads to the abandoned lighthouse.',lighthouse.id,None)]
    for subject,predicate,value,evidence,obj,situation in rows:
        proposal = memory.propose_fact(subject,predicate,value,accepted.revision_id,evidence,object_id=obj,situation_id=situation)
        memory.confirm_fact(proposal.id)
    memory.set_direction('relationship-pace','Build trust before romance.',subject_id=ivo.id)
    memory.set_direction('setting','Reveal the lighthouse gradually; stay within the approved places.')
    graph = memory.graph_snapshot()
    output = folder / 'memory-graph.html'
    export_without_overwrite(output,render_graph(graph))
    export_without_overwrite(folder / 'empty-graph.html',render_graph({'nodes':[],'edges':[],'memory_revision':0,'next_episode':1}))
    attack_graph = {'nodes':[{'id':'entity-1','kind':'character','label':'</script><script>window.attack=1</script>','status':'registry'}],'edges':[],'memory_revision':0,'next_episode':1}
    export_without_overwrite(folder / 'security-graph.html',render_graph(attack_graph))
    receipt={'fixture_only':True,'database':str(db),'graph':str(output), 'node_count':len(graph['nodes']),'edge_count':len(graph['edges']),'current_facts':len(memory.query_facts()),'directions':len(memory.directions()),'project_budget':studio.status()['project_budget']}
    export_without_overwrite(folder / 'receipt.json',json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))
