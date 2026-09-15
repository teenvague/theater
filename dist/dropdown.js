// Text-only listbox with keyboard navigation and a site-styled popup.
export class TextDropdown {
  constructor(root, label, allLabel, onChange) {
    this.root=root; this.label=label; this.allLabel=allLabel; this.onChange=onChange; this.value=''; this.options=[];
    this.trigger=document.createElement('button'); this.trigger.type='button'; this.trigger.className='dropdown-trigger';
    this.trigger.setAttribute('aria-haspopup','listbox'); this.trigger.setAttribute('aria-expanded','false');
    this.trigger.id=root.id+'-trigger';
    this.list=document.createElement('div'); this.list.className='dropdown-list'; this.list.hidden=true; this.list.id=root.id+'-list';
    this.list.setAttribute('role','listbox'); this.list.setAttribute('aria-labelledby',this.trigger.id); this.trigger.setAttribute('aria-controls',this.list.id);
    root.append(this.trigger,this.list); this.setOptions([]);
    this.trigger.addEventListener('click',()=>this.list.hidden?this.open():this.close());
    this.trigger.addEventListener('keydown',e=>{if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();this.open(e.key==='ArrowUp');}});
    this.list.addEventListener('keydown',e=>{
      const index=this.options.indexOf(document.activeElement); let next=index;
      if(e.key==='ArrowDown')next=(index+1)%this.options.length;
      else if(e.key==='ArrowUp')next=(index-1+this.options.length)%this.options.length;
      else if(e.key==='Home')next=0;
      else if(e.key==='End')next=this.options.length-1;
      else if(e.key==='Escape'){e.preventDefault();this.close(true);return;}
      else if(e.key==='Tab'){this.close(true);return;}
      else if(e.key.length===1&&e.key!==' '){
        this.typed=(Date.now()-(this.typedAt||0)<700?this.typed||'':'')+e.key.toLowerCase();this.typedAt=Date.now();
        next=this.options.findIndex(o=>o.textContent.toLowerCase().startsWith(this.typed));
      }else return;
      if(next>=0){e.preventDefault();this.options[next].focus();}
    });
    document.addEventListener('pointerdown',e=>{if(!root.contains(e.target))this.close();});
    root.addEventListener('focusout',()=>queueMicrotask(()=>{if(!root.contains(document.activeElement))this.close();}));
    root.closest('nav')?.addEventListener('scroll',()=>this.close());
    window.addEventListener('resize',()=>this.close());
  }
  setOptions(values){
    this.list.replaceChildren();this.options=[];
    for(const value of ['',...values]){
      const option=document.createElement('button');option.type='button';option.setAttribute('role','option');option.tabIndex=-1;option.dataset.value=value;
      option.textContent=value||this.allLabel;
      option.addEventListener('click',()=>{this.setValue(value);this.close(true);this.onChange(value);});
      this.options.push(option);this.list.append(option);
    }
    this.setValue(this.value);
  }
  setValue(value){this.value=value;this.trigger.textContent=this.label+': '+(value||this.allLabel);for(const option of this.options)option.setAttribute('aria-selected',String(option.dataset.value===value));}
  open(last=false){
    this.list.hidden=false;
    if(window.matchMedia('(max-width:800px)').matches){
      const rect=this.trigger.getBoundingClientRect();
      this.list.style.left=Math.max(12,Math.min(rect.left,window.innerWidth-this.list.offsetWidth-12))+'px';
      this.list.style.top=rect.bottom+'px';
      this.list.style.maxHeight=Math.max(80,Math.min(300,window.innerHeight-rect.bottom-12))+'px';
    }else{this.list.style.left='';this.list.style.top='';this.list.style.maxHeight='';}
    this.trigger.setAttribute('aria-expanded','true');const selected=this.options.find(o=>o.dataset.value===this.value);(last?this.options.at(-1):selected||this.options[0]).focus({preventScroll:true});
  }
  close(focus=false){this.list.hidden=true;this.trigger.setAttribute('aria-expanded','false');if(focus)this.trigger.focus();}
}
