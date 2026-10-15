"""Experimental native menu tree and queued retail popup/voice/animation tests.

The catalogue contains names only, never retail resource bytes. Categories use
the game's native expand/collapse and reference-counted menu rows. Actions wait
for the normal scheduled frame and an attached player, outside the debug menu.
"""
from __future__ import annotations
import hashlib
import re
import struct
from .patch import Code, dword, jump, patch_xbe as freecam_patch
from .xbe import allocate,offset,sections

VERSION='1.1.0-dev'
GROUP,POPUP,VOICE,ANIMATION,STOP,GRANT_KEY=0,1,2,3,4,5

# Names and inventory IDs verified against the EU critters_item_data table.
# The retail inventory has five dynamic key slots, not twenty. Use native
# pickup semantics and refuse a full inventory rather than extending save data.
KEY_GROUPS={
    'Feu': [('Cle Feu 1','f1k1'),('Cle Feu 2','f1k2'),('Cle Feu 3','f1k3')],
    'Air': [('Cle Air 1','a1k1'),('Cle Air 2','a1k2'),('Cle Air 3','a1k3'),
            ('Cle rouge','a6kr'),('Cle verte','a6kg'),('Cle bleue','a6kb')],
    'Terre': [('Engrenage','e2k1'),('Fusible','e2k2'),('Circuit imprime','e5k1'),('Batterie','e7k1')],
    'Eau': [('Cle Eau 1','w2k1'),('Cle Eau 2','w2k2')],
    'Mort': [('Batterie diamant','d1k1'),('Lentille','d2k1')],
    'Vie et Perathia': [('Cle Vie','l1k1'),('Cle Obsidienne 1','t1k1'),('Cle Obsidienne 2','t1k2')],
}
KEY_IDS=frozenset(key for group in KEY_GROUPS.values() for _,key in group)


def key_catalogue():
    return dict(label='Cles (inventaire : 5 places)',children=[
        dict(label=realm,children=[dict(label='Donner : '+label,kind=GRANT_KEY,key=key)
                                 for label,key in entries]) for realm,entries in KEY_GROUPS.items()])


def _row(va,group_vtable,callback):
    c=Code(va);c.emit('558bec5356578b5d0868900000006a00');c.branch('e8',0xE67CD);c.emit('50');c.branch('e8',0xE4C9F)
    c.emit('85c0');c.branch('0f84','done');c.emit('8bf0');c.branch('e8',0x1FC40)
    c.emit('8b338d781cb964000000') # ESI label, EDI row+1C (EAX still row).
    c.label('copy');c.emit('8a168817464784d2');c.branch('0f84','copied');c.emit('49');c.branch('0f85','copy');c.emit('c60700')
    c.label('copied');c.emit('8b530483fa00');c.branch('0f85','leaf')
    c.emit(b'\xC7\x00'+dword(group_vtable));c.emit('c6808c00000000')
    c.emit(b'\xC7\x80\x84\x00\x00\x00'+dword(0x12890));c.branch('e9','data')
    c.label('leaf');c.emit(b'\xC7\x80\x84\x00\x00\x00'+dword(callback))
    c.label('data');c.emit('899888000000')
    c.label('done');c.emit('5f5e5bc9c20400');return c.finish()


def _expand(va,row):
    c=Code(va);c.emit('558bec5356578bf98b99880000008b730c8b5b10')
    c.label('loop');c.emit('85db');c.branch('0f84','done');c.emit('56')
    c.branch('e8',row);c.emit('85c0');c.branch('0f84','next')
    c.emit('568bf08bc7');c.branch('e8',0x1FCA0);c.emit('5e')
    c.label('next');c.emit('83c6144b');c.branch('e9','loop')
    c.label('done');c.emit('5f5e5bc9c20400');return c.finish()


def _root_append(va,row,descriptors):
    c=Code(va);c.emit('558bec5356578b7d08')
    for descriptor in descriptors:
        c.emit(b'\x68'+dword(descriptor));c.branch('e8',row);c.emit('85c0');c.branch('0f84','done')
        c.emit('8bf0');c.branch('e8',0x1FBB0)
    c.label('done');c.emit('5f5e5bc9c20400');return c.finish()


def _state_expand(va,row,descriptor):
    """Keep the four native magic rows, then append a real nested key group."""
    c=Code(va);c.emit('558bec5356578bd9ff7508');c.branch('e8',0x135A0)
    c.emit(b'\x68'+dword(descriptor));c.branch('e8',row);c.emit('85c0');c.branch('0f84','done')
    c.emit('8bf08bc3');c.branch('e8',0x1FCA0)
    c.label('done');c.emit('5f5e5bc9c20400');return c.finish()


def _callback(va,state):
    c=Code(va);c.emit('558bec5356578bf98b5d088b87b800000085c0');c.branch('0f84','done')
    c.emit('8bc88b10ff1285c0');c.branch('0f84','done') # Interface vtable0 returns current World.
    c.emit('83b8cc00000000');c.branch('0f84','done')
    c.emit(b'\xA3'+dword(state+8));c.emit(b'\x89\x1D'+dword(state))
    c.emit('8b87b4000000');c.emit(b'\xA3'+dword(state+4));c.emit('85c0');c.branch('0f84','done')
    c.emit('c7401c03000000') # Native state3 closes/destroys the top debug window next frame.
    c.label('done');c.emit('5f5e5bc9c20400');return c.finish()


def _stop_sound(c,state,label):
    c.emit(b'\x8B\x0D'+dword(state+20));c.emit('85c9');c.branch('0f84',label)
    c.emit('8b11ff5238');c.emit(b'\x8B\x0D'+dword(state+20));c.emit('8b11ff5244')
    c.emit(b'\xC7\x05'+dword(state+20)+dword(0));c.label(label)


def _pump(va,state,grant_key):
    c=Code(va);c.emit('558bec535657')
    c.emit(b'\xA1'+dword(state));c.emit(b'\x0B\x05'+dword(state+12));c.emit(b'\x0B\x05'+dword(state+20));c.emit('85c0');c.branch('0f84','done')
    c.emit('8b45088b784485ff');c.branch('0f84','done')
    c.emit(b'\x3B\x3D'+dword(state+8));c.branch('0f84','live_world')
    c.emit(b'\x3B\x3D'+dword(state+16));c.branch('0f84','live_world')
    c.emit(b'\x3B\x3D'+dword(state+28));c.branch('0f85','done')
    c.label('live_world')
    c.emit('8bb7cc00000085f6');c.branch('0f84','done')
    c.emit(b'\x83\x3D'+dword(state+12)+b'\x00');c.branch('0f84','check_audio')
    c.emit(b'\x3B\x35'+dword(state+12));c.branch('0f85','clear_old_actor')
    c.emit(b'\x3B\x3D'+dword(state+16));c.branch('0f84','check_audio')
    c.label('clear_old_actor');c.emit(b'\xC7\x05'+dword(state+12)+dword(0))
    c.label('check_audio');c.emit(b'\x83\x3D'+dword(state+20)+b'\x00');c.branch('0f84','queued')
    c.emit(b'\x3B\x3D'+dword(state+28));c.branch('0f84','queued')
    _stop_sound(c,state,'queued')
    c.emit(b'\x8B\x1D'+dword(state));c.emit('85db');c.branch('0f84','done')
    c.emit(b'\x3B\x3D'+dword(state+8));c.branch('0f85','cancel')
    c.emit(b'\xA1'+dword(state+4));c.emit('85c0');c.branch('0f84','cancel')
    c.emit('83781c02');c.branch('0f83','done') # Remain outside menu states2/3/4.
    c.emit('8b4b0483f901');c.branch('0f85','dispatch')
    c.emit('8b87ec00000085c0');c.branch('0f84','done');c.emit('80780400');c.branch('0f85','done')
    c.label('dispatch');c.emit(b'\xC7\x05'+dword(state)+dword(0))
    c.emit('8b4b0483f904');c.branch('0f84','stop')
    c.emit('83f905');c.branch('0f84','grant_key')
    c.emit('83f901');c.branch('0f85','lookup')
    c.emit('ff73088b8fec000000');c.branch('e8',0x19650);c.branch('e9','done')
    c.label('lookup');c.emit('6a0233c0')
    c.emit('83f903');c.branch('0f85','soundkey');c.emit('b862616e6d')
    c.label('soundkey');c.emit('508b4b08');c.branch('e8',0xA5E20) # key ECX, [type,wait].
    c.emit('83f8ff');c.branch('0f84','done');c.emit('837b0403');c.branch('0f84','animation')
    c.emit('50');_stop_sound(c,state,'old_audio_stopped');c.emit('58')
    c.emit('6a006a0050');c.emit(b'\x68'+dword(0x1AC870));c.branch('e8',0xA1DF0)
    c.emit('85c0');c.branch('0f84','done');c.emit(b'\xA3'+dword(state+20))
    c.emit(b'\x89\x3D'+dword(state+28));c.emit('8bc88b10689a99993fff520c');c.emit(b'\x8B\x0D'+dword(state+20));c.emit('8b01ff5030');c.branch('e9','done')
    c.label('animation');c.emit('8b8e7c01000085c9');c.branch('0f84','done')
    c.emit('81be0002000000020000');c.branch('0f83','done')
    c.emit(b'\x89\x35'+dword(state+12));c.emit(b'\x89\x3D'+dword(state+16));c.emit('6a015051');c.branch('e8',0xCAEC0);c.branch('e9','done')
    c.label('stop');_stop_sound(c,state,'audio_stopped')
    c.emit(b'\xA1'+dword(state+12));c.emit('3bc6');c.branch('0f85','clear')
    c.emit(b'\xC7\x05'+dword(state+12)+dword(0));c.emit('6a00ffb60002000056');c.branch('e8',0x42910)
    c.label('clear');c.emit(b'\xC7\x05'+dword(state+12)+dword(0));c.branch('e9','done')
    c.label('grant_key');c.emit('8b43088b005057');c.branch('e8',grant_key);c.branch('e9','done')
    c.label('cancel');c.emit(b'\xC7\x05'+dword(state)+dword(0))
    c.label('done');c.emit('5f5e5bc9c20400');return c.finish()


def _grant_key(va,full_message):
    """[World, FourCC] -> native add-one; never replace another held key."""
    c=Code(va);c.emit('558bec5356578b7d088bb7e000000085f6');c.branch('0f84','done')
    c.emit('39bed8010000');c.branch('0f85','done') # State must belong to this world.
    c.emit('8b5d0c8d869801000033d2b905000000')
    c.label('slot');c.emit('3918');c.branch('0f85','other')
    c.emit('83780400');c.branch('0f8f','done');c.branch('e9','pickup') # Already owned: idempotent.
    c.label('other');c.emit('837804007f028bd0') # Remember a free slot, without writing it.
    c.emit('83c00c49');c.branch('0f85','slot')
    c.emit('85d2');c.branch('0f85','pickup')
    c.emit('8b8fec00000085c9');c.branch('0f84','done');c.emit('80790400');c.branch('0f85','done')
    c.emit(b'\x68'+dword(full_message));c.branch('e8',0x19650);c.branch('e9','done')
    c.label('pickup');c.emit('6a018bc38bce');c.branch('e8',0x587B0)
    c.label('done');c.emit('5f5e5bc9c20800');return c.finish()


def _frame(va,pump):
    c=Code(va);c.emit('9c6056');c.branch('e8',pump);c.emit('619d');c.branch('e9',0x66360);return c.finish()


def _animation_gate(va,state,trampoline):
    c=Code(va);c.emit('9c50528b442410') # entry [return,actor,index,flags]; after pushes actor atesp16.
    c.emit(b'\x3B\x05'+dword(state+12));c.branch('0f85','normal')
    c.emit('8b9054010000');c.emit(b'\x3B\x15'+dword(state+16));c.branch('0f85','normal')
    c.emit('5a589dc20c00');c.label('normal');c.emit('5a589d');c.branch('e9',trampoline);return c.finish()


def _input_gate(va,state,original_gate):
    c=Code(va);c.emit('9c60558b4520') # EBP PlayerPhysics -> live actor+20; extra pushEBP? undone before exit.
    c.emit(b'\x3B\x05'+dword(state+12));c.branch('0f85','normal')
    c.emit('85c0');c.branch('0f84','normal');c.emit('8b9054010000');c.emit(b'\x3B\x15'+dword(state+16));c.branch('0f85','normal')
    c.emit('5d619d');c.branch('e9',0x84FFE)
    c.label('normal');c.emit('5d619d');c.branch('e9',original_gate);return c.finish()


def patch_xbe(source,catalog):
    """Create native submenu patch from pristine EU XBE and a names-only tree.

    Descriptor: {label, children:[...]} or {label, kind:1..5, key:<asset key>}.
    Current native oracle BODY has no BANM clips; do not invent catalogue clips.
    """
    base,freecam=freecam_patch(source)
    call=offset(source,0x66497)
    if source[call:call+5]!=b'\xE8'+struct.pack('<i',0x66360-0x6649C):
        raise ValueError('Unexpected native scheduled graph call.')
    out,raw,va=allocate(base,65536)
    out[raw:raw+8]=b'DBGLAB01';used=64;state=va+16;routines={}
    def store(blob,alignment=16):
        nonlocal used
        used=(used+alignment-1)//alignment*alignment;address=va+used
        if used+len(blob)>65536:raise ValueError('Native test catalogue exceeds bounded section.')
        out[raw+used:raw+used+len(blob)]=blob;used+=len(blob);return address
    def add(name,builder):
        nonlocal used
        used=(used+15)//16*16;address=va+used;body=builder(address);actual=store(body)
        assert actual==address;routines[name]=dict(va=address,size=len(body));return address
    vtable=store(b'\0'*20);row_stub=store(b'\0'*256)
    expand=add('expand',lambda p:_expand(p,row_stub));callback=add('callback',lambda p:_callback(p,state))
    for i,v in enumerate([0x12010,0x200F0,0x20110,expand,0x129B0]):struct.pack_into('<I',out,raw+vtable-va+i*4,v)
    row_body=_row(row_stub,vtable,callback)
    if len(row_body)>256:raise ValueError('Row factory overflow.')
    out[raw+row_stub-va:raw+row_stub-va+len(row_body)]=row_body;routines['row']=dict(va=row_stub,size=len(row_body))
    def descriptors(entries):
        if not isinstance(entries,list) or len(entries)>150:raise ValueError('Invalid submenu count.')
        rows=[]
        for item in entries:
            label=item['label'].encode('ascii')
            if not 1<=len(label)<=90 or any(c<32 for c in label):raise ValueError('Menu label must be short printable ASCII.')
            label_va=store(label+b'\0',1)
            if 'children'in item:
                child_array=descriptors(item['children']);row=(label_va,GROUP,0,child_array,len(item['children']))
            else:
                kind=item['kind'];key=item.get('key','')
                if kind not in [POPUP,VOICE,ANIMATION,STOP,GRANT_KEY] or not isinstance(key,str) or len(key)>180 or not re.fullmatch(r'[A-Za-z0-9_/. -]*',key):raise ValueError('Invalid native action key.')
                if kind==GRANT_KEY and key not in KEY_IDS:raise ValueError('Unverified inventory key ID.')
                key_va=store(key.encode('ascii')+b'\0',1);row=(label_va,kind,key_va,0,0)
            rows.append(struct.pack('<5I',*row))
        return store(b''.join(rows),4)
    keys=key_catalogue();keys_top=descriptors([keys])
    state_expand=add('stateExpand',lambda p:_state_expand(p,row_stub,keys_top))
    state_vtable=offset(source,0x1A3C24)
    if struct.unpack_from('<I',source,state_vtable)[0]!=0x135A0:raise ValueError('Unexpected Game state expansion.')
    struct.pack_into('<I',out,offset(out,0x1A3C24),state_expand)
    top=descriptors(catalog);root_append=add('append',lambda p:_root_append(p,row_stub,[top+i*20 for i in range(len(catalog))]))
    full_message=store(b'loc/english/popups/6keys\0',1)
    grant_key=add('grantKey',lambda p:_grant_key(p,full_message))
    pump=add('pump',lambda p:_pump(p,state,grant_key));frame=add('frame',lambda p:_frame(p,pump))
    stolen=source[offset(source,0x42910):offset(source,0x42910)+7]
    if stolen!=bytes.fromhex('5155568b742410'):raise ValueError('Unexpected actor animation entry.')
    trampoline=add('animTrampoline',lambda p:stolen+jump(p+len(stolen),0x42917,5))
    gate=add('animationGate',lambda p:_animation_gate(p,state,trampoline))
    input_gate=add('simulationInput',lambda p:_input_gate(p,state,freecam['routines']['playerInputGate']['va']))
    epilogue=bytes.fromhex('8b8424e00700005f5e5b81c4d0070000c20c00')
    factory=freecam['routines']['menuFactory'];tail_address=factory['va']+factory['size']-len(epilogue)
    if out[offset(out,tail_address):offset(out,tail_address)+len(epilogue)]!=epilogue:raise ValueError('Freecam factory epilogue drifted.')
    def tail(p):
        c=Code(p);c.emit('8b8424e00700009c6050');c.branch('e8',root_append);c.emit('619d');c.emit(epilogue);return c.finish()
    tail_va=add('factoryTail',tail)
    edits=[(tail_address,jump(tail_address,tail_va,len(epilogue))),
                         (0x66497,b'\xE8'+struct.pack('<i',frame-0x6649C)),
                         (0x42910,jump(0x42910,gate,7)),(0x8500D,jump(0x8500D,input_gate,6))]
    for address,body in edits:
        at=offset(out,address);out[at:at+len(body)]=body
    title=store(('Commande menue - '+VERSION).encode('ascii')+b'\0',1)
    at=offset(out,0x1395F);out[at:at+5]=b'\xB8'+dword(title)
    ranges=[(offset(base,address),len(body))for address,body in edits]+[(offset(base,0x1395F),5),(offset(base,0x1A3C24),4)]
    for section in sections(base)[1]:
        start=section['raw'];end=start+section['raw_size'];expected=bytearray(base[start:end])
        for pos,length in ranges:
            if start<=pos<end:expected[pos-start:pos-start+length]=out[pos:pos+length]
        if expected!=out[start:end]:raise ValueError('Unexpected change outside native laboratory hooks.')
    return bytes(out),dict(version=VERSION,sourceSha256=hashlib.sha256(source).hexdigest(),outputSha256=hashlib.sha256(out).hexdigest(),
        stateVA=state,routines=routines,sectionVA=va,sectionRaw=raw,sectionUsedBytes=used,catalog=catalog,
        nativeGameTested=False,oracleSkeletalClipsPresent=False,frameCallerReturn=0x6649C,freecam=freecam,
        keys=keys,keyInventoryCapacity=5,keyAction='native pickup; owned keys unchanged; full inventory refused',
        hooks=[dict(offset=pos,bytes=length)for pos,length in ranges],otherBaselineSectionBytesPreserved=True)
