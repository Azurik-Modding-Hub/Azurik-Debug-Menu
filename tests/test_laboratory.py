"""Native menu/ABI regressions. Retail bytes remain local and optional."""
import os
from pathlib import Path
import struct
import pytest
from unicorn import x86_const as r
import test_x86 as native
from freecam.laboratory import patch_xbe, VERSION, POPUP, VOICE, ANIMATION, STOP, GRANT_KEY, KEY_IDS

CATALOG=[dict(label='Text boxes',children=[dict(label='Training',kind=POPUP,key='loc/english/popups/training1')]),
         dict(label='Oracles',children=[dict(label='Eldwin',children=[dict(label='Water realm',kind=VOICE,key='loc/english/speech/eld_level_intros/eld_w1_hint1')])]),
         dict(label='Animations',children=[dict(label='Azurik idle',kind=ANIMATION,key='characters/garret4/idle'),dict(label='Stop test',kind=STOP)])]

@pytest.fixture(scope='module')
def lab():
    path=os.environ.get('AZURIK_XBE')
    if not path:pytest.skip('Optional native EU audit; provide your own original XBE.')
    return patch_xbe(Path(path).read_bytes(),CATALOG)


def test_native_root_keeps_original_rows_and_has_three_real_groups(lab,monkeypatch):
    image,metadata=lab
    monkeypatch.setattr(native,'ROOT_MENU_TITLE','Commande menue - '+VERSION)
    u,rows,allocations=native.construct_native_root_menu(image)
    assert [row['label'] for row in rows]==['Change level...','Play Movie...','Game state...','Freecam','Text boxes','Oracles','Animations']
    assert all(row['callback']==0x12890 for row in rows[4:])
    # Real generic expansion callback and native child insertion, including a
    # nested category. Only heap allocation boundaries are intercepted.
    next_heap=[0x725000]
    def heap(uc):uc.reg_write(r.UC_X86_REG_EAX,native.HEAP);native.return_from(uc)
    def reserve(n):
        at=next_heap[0];next_heap[0]+=(n+15)&~15;assert next_heap[0]<0x730000;return at
    def alloc(uc):
        sp=uc.reg_read(r.UC_X86_REG_ESP);uc.reg_write(r.UC_X86_REG_EAX,reserve(native.get(uc,sp+12)));native.return_from(uc,12)
    def vector(uc):uc.reg_write(r.UC_X86_REG_EAX,reserve(uc.reg_read(r.UC_X86_REG_EAX)));native.return_from(uc)
    handlers={0xE67CD:heap,0xE4C9F:alloc,0x185E0:vector}
    context=native.CONTEXT
    native.put(u,context+0x9c,0x72e000);native.put(u,context+0xa0,0x72e000);native.put(u,context+0xa4,0x72e100)
    def expand(row):
        native.put(u,native.STACK,native.EXIT);native.put(u,native.STACK+4,0)
        u.reg_write(r.UC_X86_REG_ESP,native.STACK);u.reg_write(r.UC_X86_REG_ECX,context);u.reg_write(r.UC_X86_REG_EDX,row)
        native.run_until(u,0x12890,handlers,count=30000)
        assert u.reg_read(r.UC_X86_REG_ESP)==native.STACK+8
        assert bytes(u.mem_read(row+0x8c,1))==b'\1'
        begin,end=native.get(u,row+0x10),native.get(u,row+0x14)
        return [native.get(u,p) for p in range(begin,end,4)]
    child=expand(rows[4]['address'])[0]
    assert bytes(u.mem_read(child+0x1c,30)).split(b'\0')[0]==b'Training'
    assert native.get(u,child+0x84)==metadata['routines']['callback']['va']
    nested=expand(rows[5]['address'])[0]
    oracle=expand(nested)[0]
    assert bytes(u.mem_read(oracle+0x1c,30)).split(b'\0')[0]==b'Water realm'
    # Execute the untouched magic-state expansion as well as the new wrapper.
    world=0x70a000;game=0x70b000
    native.put(u,native.INTERFACE,native.PARENT);native.put(u,native.PARENT,native.CODE)
    native.put(u,world+0xe0,game)
    def get_world(uc):uc.reg_write(r.UC_X86_REG_EAX,world);native.return_from(uc)
    handlers[native.CODE]=get_world
    state_rows=expand(rows[2]['address'])
    labels=[bytes(u.mem_read(row+0x1c,100)).split(b'\0')[0] for row in state_rows]
    assert labels[:4]==[b'Earth magic level: 0',b'Air magic level: 0',b'Fire magic level: 0',b'Water magic level: 0']
    assert labels[4]==b'Cles (inventaire : 5 places)'
    assert len(expand(state_rows[4]))==6


def test_leaf_queues_and_native_input_callback_closes_menu(lab):
    image,m=lab;u=native.machine(image);state=m['stateVA']
    native.put(u,native.CONTEXT+0xb4,native.OWNER);native.put(u,native.CONTEXT+0xb8,native.INTERFACE)
    native.put(u,native.INTERFACE,native.PARENT);native.put(u,native.PARENT,native.CODE)
    native.put(u,native.OWNER+0x1c,2)
    world=0x70a000;native.put(u,world+0xcc,0x70b000)
    def get_world(uc):uc.reg_write(r.UC_X86_REG_EAX,world);native.return_from(uc)
    descriptor=0x70c000;native.put(u,descriptor+4,POPUP)
    native.put(u,native.ROW,0x1A3C08);native.put(u,native.ROW+0x84,m['routines']['callback']['va']);native.put(u,native.ROW+0x88,descriptor)
    native.put(u,native.STACK,native.EXIT);native.put(u,native.STACK+4,native.CONTEXT)
    u.reg_write(r.UC_X86_REG_ESP,native.STACK);u.reg_write(r.UC_X86_REG_ECX,native.ROW)
    native.run_until(u,0x200F0,{native.CODE:get_world},count=1000)
    assert native.get(u,state)==descriptor and native.get(u,state+8)==world
    assert native.get(u,native.OWNER+0x1c)==3
    assert u.reg_read(r.UC_X86_REG_ESP)==native.STACK+8


def test_idle_laboratory_never_reads_an_unattached_graph_world(lab):
    image,m=lab;u=native.machine(image);graph=0x70a000
    native.put(u,graph+0x44,0xdead0000)
    native.put(u,native.STACK,native.EXIT);native.put(u,native.STACK+4,graph)
    u.reg_write(r.UC_X86_REG_ESP,native.STACK)
    native.run_until(u,m['routines']['pump']['va'],count=1000)
    assert u.reg_read(r.UC_X86_REG_ESP)==native.STACK+8


@pytest.mark.parametrize('kind',[POPUP,VOICE,ANIMATION,STOP,GRANT_KEY])
def test_queued_action_waits_for_closed_menu_and_calls_native_abi(lab,kind):
    image,m=lab;u=native.machine(image);state=m['stateVA'];graph=0x70a000;world=0x70b000;actor=0x70c000;desc=0x70d000;controller=0x70e000;anim=0x70f000
    native.put(u,graph+0x44,world);native.put(u,world+0xcc,actor);native.put(u,world+0xec,controller)
    native.put(u,actor+0x17c,anim);native.put(u,actor+0x200,0)
    native.put(u,state,desc);native.put(u,state+4,native.OWNER);native.put(u,state+8,world)
    key=native.CODE+0x100;u.mem_write(key,b'example/key\0');native.put(u,desc+4,kind);native.put(u,desc+8,key)
    native.put(u,native.OWNER+0x1c,2);calls=[]
    def invoke():
        native.put(u,native.STACK,native.EXIT);native.put(u,native.STACK+4,graph)
        u.reg_write(r.UC_X86_REG_ESP,native.STACK)
        return native.run_until(u,m['routines']['pump']['va'],handlers,count=3000)
    def popup(uc):
        assert uc.reg_read(r.UC_X86_REG_ECX)==controller
        sp=uc.reg_read(r.UC_X86_REG_ESP);assert native.get(uc,sp+4)==key
        calls.append('popup');native.return_from(uc,4)
    def lookup(uc):
        assert uc.reg_read(r.UC_X86_REG_ECX)==key
        calls.append('lookup');uc.reg_write(r.UC_X86_REG_EAX,1234);native.return_from(uc,8)
    sound=native.CODE+0x200;vt=native.CODE+0x300
    native.put(u,sound,vt);native.put(u,vt+0xc,native.CODE+0x400);native.put(u,vt+0x30,native.CODE+0x500)
    def factory(uc):
        sp=uc.reg_read(r.UC_X86_REG_ESP);assert [native.get(uc,sp+i) for i in [4,8,12,16]]==[0x1AC870,1234,0,0]
        calls.append('factory');uc.reg_write(r.UC_X86_REG_EAX,sound);native.return_from(uc,16)
    def volume(uc):calls.append('volume');native.return_from(uc,4)
    def play(uc):calls.append('play');native.return_from(uc)
    def animate(uc):
        sp=uc.reg_read(r.UC_X86_REG_ESP);assert [native.get(uc,sp+i) for i in [4,8,12]]==[anim,1234,1]
        calls.append('animation');native.return_from(uc,12)
    def grant(uc):
        sp=uc.reg_read(r.UC_X86_REG_ESP)
        assert native.get(uc,sp+4)==world and native.get(uc,sp+8)==int.from_bytes(b'exam','little')
        calls.append('key');native.return_from(uc,8)
    handlers={0x19650:popup,0xA5E20:lookup,0xA1DF0:factory,native.CODE+0x400:volume,native.CODE+0x500:play,0xCAEC0:animate,m['routines']['grantKey']['va']:grant}
    invoke();assert not calls and native.get(u,state)==desc
    native.put(u,native.OWNER+0x1c,0);invoke()
    assert native.get(u,state)==0 and u.reg_read(r.UC_X86_REG_ESP)==native.STACK+8
    assert calls=={POPUP:['popup'],VOICE:['lookup','factory','volume','play'],ANIMATION:['lookup','animation'],STOP:[],GRANT_KEY:['key']}[kind]


@pytest.mark.parametrize('key',sorted(KEY_IDS))
def test_grant_runs_retail_inventory_code_and_changes_only_selected_key(lab,key):
    image,m=lab;u=native.machine(image);world=0x70a000;game=0x70b000;actor=0x70c000
    native.put(u,world+0xe0,game);native.put(u,world+0xcc,actor);native.put(u,game+0x1d8,world)
    # Existing tutorial-seen bit avoids an unrelated first-key popup here.
    native.put(u,game+0x14,0x8000)
    for slot in range(5):native.put(u,game+0x198+slot*12+8,0xffffffff)
    native.put(u,game+0x198,int.from_bytes(b'test','little'));native.put(u,game+0x19c,2)
    before=bytes(u.mem_read(game,0x1dc))
    def invoke():
        for i,value in enumerate([native.EXIT,world,int.from_bytes(key.encode(),'little')]):native.put(u,native.STACK+4*i,value)
        u.reg_write(r.UC_X86_REG_ESP,native.STACK)
        native.run_until(u,m['routines']['grantKey']['va'],count=3000)
        assert u.reg_read(r.UC_X86_REG_ESP)==native.STACK+12
    invoke()
    after=bytes(u.mem_read(game,0x1dc));slot=game+0x1a4 # First empty slot selected by native 58090.
    assert native.get(u,slot)==int.from_bytes(key.encode(),'little') and native.get(u,slot+4)==1
    allowed=set(range(slot-game,slot-game+8))
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(before,after)))
    invoke();assert bytes(u.mem_read(game,0x1dc))==after # Giving an owned key does not multiply it.


def test_full_key_inventory_is_preserved_and_uses_original_full_message(lab):
    image,m=lab;u=native.machine(image);world=0x70a000;game=0x70b000;controller=0x70c000
    native.put(u,world+0xe0,game);native.put(u,game+0x1d8,world);native.put(u,world+0xec,controller)
    for i in range(5):
        native.put(u,game+0x198+i*12,int.from_bytes(('x%03d'%i).encode(),'little'));native.put(u,game+0x19c+i*12,1)
    before=bytes(u.mem_read(game,0x1dc));calls=[]
    def popup(uc):
        sp=uc.reg_read(r.UC_X86_REG_ESP);key=native.get(uc,sp+4)
        assert bytes(uc.mem_read(key,24)).split(b'\0')[0]==b'loc/english/popups/6keys'
        assert uc.reg_read(r.UC_X86_REG_ECX)==controller
        calls.append('full');native.return_from(uc,4)
    for i,value in enumerate([native.EXIT,world,int.from_bytes(b'e7k1','little')]):native.put(u,native.STACK+4*i,value)
    u.reg_write(r.UC_X86_REG_ESP,native.STACK)
    native.run_until(u,m['routines']['grantKey']['va'],{0x19650:popup},count=3000)
    assert calls==['full'] and bytes(u.mem_read(game,0x1dc))==before


def test_unverified_inventory_key_is_rejected():
    with pytest.raises(ValueError,match='Unverified inventory'):
        path=os.environ.get('AZURIK_XBE')
        if not path:pytest.skip('Optional native EU audit.')
        patch_xbe(Path(path).read_bytes(),[dict(label='Unknown key',kind=GRANT_KEY,key='bad1')])


def test_frame_tail_preserves_the_actual_scheduler_caller_and_stack(lab):
    image,m=lab;u=native.machine(image);graph=0x70a000;calls=[]
    native.put(u,native.STACK,graph);u.reg_write(r.UC_X86_REG_ESP,native.STACK);u.reg_write(r.UC_X86_REG_ESI,graph)
    def graph_update(uc):
        sp=uc.reg_read(r.UC_X86_REG_ESP)
        assert native.get(uc,sp)==0x6649c and native.get(uc,sp+4)==graph
        calls.append('graph');native.return_from(uc,4)
    native.run_until(u,0x66497,{0x66360:graph_update},targets=(0x6649c,),count=1000)
    assert calls==['graph'] and u.reg_read(r.UC_X86_REG_ESP)==native.STACK+4


def test_stop_restores_native_animation_selection_before_restoring_controls(lab):
    image,m=lab;u=native.machine(image);state=m['stateVA'];graph=0x70a000;world=0x70b000;actor=0x70c000;desc=0x70d000
    native.put(u,graph+0x44,world);native.put(u,world+0xcc,actor);native.put(u,actor+0x154,world);native.put(u,actor+0x200,7)
    for at,val in [(state,desc),(state+4,native.OWNER),(state+8,world),(state+12,actor),(state+16,world),(desc+4,STOP)]:native.put(u,at,val)
    native.put(u,native.STACK,native.EXIT);native.put(u,native.STACK+4,graph);u.reg_write(r.UC_X86_REG_ESP,native.STACK)
    calls=[]
    def restore(uc):
        sp=uc.reg_read(r.UC_X86_REG_ESP)
        assert [native.get(uc,sp+i)for i in [4,8,12]]==[actor,7,0]
        assert native.get(uc,state+12)==0
        calls.append('restore');native.return_from(uc,12)
    # Our actual animation gate must reach the original entry trampoline.
    native.run_until(u,m['routines']['pump']['va'],{m['routines']['animTrampoline']['va']:restore},count=3000)
    assert calls==['restore'] and native.get(u,state+12)==0
