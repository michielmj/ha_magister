/*!
 * Magister Homework planner card
 * Copyright (c) the ha_magister contributors. MIT License.
 * https://github.com/michielmj/ha_magister
 *
 * Includes Lit (lit, lit-html, lit-element and @lit/reactive-element), https://lit.dev
 *
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice, this
 *    list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 * 3. Neither the name of the copyright holder nor the names of its contributors
 *    may be used to endorse or promote products derived from this software
 *    without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
var e=globalThis,t=e.ShadowRoot&&(e.ShadyCSS===void 0||e.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,n=Symbol(),r=/* @__PURE__ */ new WeakMap,i=class{constructor(e,t,r){if(this._$cssResult$=!0,r!==n)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,n=this.t;if(t&&e===void 0){let t=n!==void 0&&n.length===1;t&&(e=r.get(n)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),t&&r.set(n,e))}return e}toString(){return this.cssText}},a=e=>new i(typeof e==`string`?e:e+``,void 0,n),o=(e,...t)=>new i(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,n),s=(n,r)=>{if(t)n.adoptedStyleSheets=r.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let t of r){let r=document.createElement(`style`),i=e.litNonce;i!==void 0&&r.setAttribute(`nonce`,i),r.textContent=t.cssText,n.appendChild(r)}},c=t?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return a(t)})(e):e,{is:l,defineProperty:u,getOwnPropertyDescriptor:d,getOwnPropertyNames:ee,getOwnPropertySymbols:te,getPrototypeOf:ne}=Object,f=globalThis,re=f.trustedTypes,ie=re?re.emptyScript:``,ae=f.reactiveElementPolyfillSupport,p=(e,t)=>e,oe={toAttribute(e,t){switch(t){case Boolean:e=e?ie:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},se=(e,t)=>!l(e,t),ce={attribute:!0,type:String,converter:oe,reflect:!1,useDefault:!1,hasChanged:se};Symbol.metadata??=Symbol(`metadata`),f.litPropertyMetadata??=/* @__PURE__ */ new WeakMap;var m=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=ce){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&u(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=d(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??ce}static _$Ei(){if(this.hasOwnProperty(p(`elementProperties`)))return;let e=ne(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(p(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(p(`properties`))){let e=this.properties,t=[...ee(e),...te(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=/* @__PURE__ */ new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(c(e))}else e!==void 0&&t.push(c(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=/* @__PURE__ */ new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=/* @__PURE__ */ new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=/* @__PURE__ */ new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return s(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?oe:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?oe:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??se)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=/* @__PURE__ */ new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=/* @__PURE__ */ new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=/* @__PURE__ */ new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};m.elementStyles=[],m.shadowRootOptions={mode:`open`},m[p(`elementProperties`)]=/* @__PURE__ */ new Map,m[p(`finalized`)]=/* @__PURE__ */ new Map,ae?.({ReactiveElement:m}),(f.reactiveElementVersions??=[]).push(`2.1.2`);var le=globalThis,ue=e=>e,h=le.trustedTypes,de=h?h.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,fe=`$lit$`,g=`lit$${Math.random().toFixed(9).slice(2)}$`,_=`?`+g,pe=`<${_}>`,v=document,y=()=>v.createComment(``),b=e=>e===null||typeof e!=`object`&&typeof e!=`function`,me=Array.isArray,he=e=>me(e)||typeof e?.[Symbol.iterator]==`function`,ge=`[ 	
\f\r]`,x=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,_e=/-->/g,ve=/>/g,S=RegExp(`>|${ge}(?:([^\\s"'>=/]+)(${ge}*=${ge}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),ye=/'/g,be=/"/g,xe=/^(?:script|style|textarea|title)$/i,C=(e=>(t,...n)=>({_$litType$:e,strings:t,values:n}))(1),w=Symbol.for(`lit-noChange`),T=Symbol.for(`lit-nothing`),Se=/* @__PURE__ */ new WeakMap,E=v.createTreeWalker(v,129);function Ce(e,t){if(!me(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return de===void 0?t:de.createHTML(t)}var we=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=x;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===x?c[1]===`!--`?o=_e:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=S):(xe.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=S):o=ve:o===S?c[0]===`>`?(o=i??x,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?S:c[3]===`"`?be:ye):o===be||o===ye?o=S:o===_e||o===ve?o=x:(o=S,i=void 0);let d=o===S&&e[t+1].startsWith(`/>`)?` `:``;a+=o===x?n+pe:l>=0?(r.push(s),n.slice(0,l)+fe+n.slice(l)+g+d):n+g+(l===-2?t:d)}return[Ce(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},Te=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=we(t,n);if(this.el=e.createElement(l,r),E.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=E.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(fe)){let t=u[o++],n=i.getAttribute(e).split(g),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?De:r[1]===`?`?Oe:r[1]===`@`?ke:k}),i.removeAttribute(e)}else e.startsWith(g)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(xe.test(i.tagName)){let e=i.textContent.split(g),t=e.length-1;if(t>0){i.textContent=h?h.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],y()),E.nextNode(),c.push({type:2,index:++a});i.append(e[t],y())}}}else if(i.nodeType===8){if(i.data===_)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(g,e+1))!==-1;)c.push({type:7,index:a}),e+=g.length-1}}a++}}static createElement(e,t){let n=v.createElement(`template`);return n.innerHTML=e,n}};function D(e,t,n=e,r){if(t===w)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=b(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=D(e,i._$AS(e,t.values),i,r)),t}var Ee=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??v).importNode(t,!0);E.currentNode=r;let i=E.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new O(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new Ae(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=E.nextNode(),a++)}return E.currentNode=v,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},O=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=T,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=D(this,e,t),b(e)?e===T||e==null||e===``?(this._$AH!==T&&this._$AR(),this._$AH=T):e!==this._$AH&&e!==w&&this._(e):e._$litType$===void 0?e.nodeType===void 0?he(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==T&&b(this._$AH)?this._$AA.nextSibling.data=e:this.T(v.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=Te.createElement(Ce(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new Ee(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=Se.get(e.strings);return t===void 0&&Se.set(e.strings,t=new Te(e)),t}k(t){me(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(y()),this.O(y()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=ue(e).nextSibling;ue(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},k=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=T,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(/* @__PURE__ */ new String),this.strings=n):this._$AH=T}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=D(this,e,t,0),a=!b(e)||e!==this._$AH&&e!==w,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=D(this,r[n+o],t,o),s===w&&(s=this._$AH[o]),a||=!b(s)||s!==this._$AH[o],s===T?e=T:e!==T&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===T?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},De=class extends k{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===T?void 0:e}},Oe=class extends k{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==T)}},ke=class extends k{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=D(this,e,t,0)??T)===w)return;let n=this._$AH,r=e===T&&n!==T||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==T&&(n===T||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},Ae=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){D(this,e)}},je={M:fe,P:g,A:_,C:1,L:we,R:Ee,D:he,V:D,I:O,H:k,N:Oe,U:ke,B:De,F:Ae},Me=le.litHtmlPolyfillSupport;Me?.(Te,O),(le.litHtmlVersions??=[]).push(`3.3.3`);var Ne=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new O(t.insertBefore(y(),e),e,void 0,n??{})}return i._$AI(e),i},Pe=globalThis,A=class extends m{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Ne(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return w}};A._$litElement$=!0,A.finalized=!0,Pe.litElementHydrateSupport?.({LitElement:A});var Fe=Pe.litElementPolyfillSupport;Fe?.({LitElement:A}),(Pe.litElementVersions??=[]).push(`4.2.2`);var j=[0,25,50,75,100];function Ie(e){return Number.isFinite(e)?Math.min(Math.round(Math.min(Math.max(e,0),100)/25)*25,100):0}function Le(e){if(!e.completed)return 100;let t=Math.round(e.last_partial);return Math.min(Math.max(Number.isFinite(t)?t:0,0),99)}var Re=/^(\d{4})-(\d{2})-(\d{2})$/;function M(e){let t=Re.exec(e);return t?new Date(Date.UTC(Number(t[1]),Number(t[2])-1,Number(t[3]))):/* @__PURE__ */ new Date(NaN)}function N(e,t){let n=M(e);return n.setUTCDate(n.getUTCDate()+t),n.toISOString().slice(0,10)}function ze(e,t){try{let n=new Intl.DateTimeFormat(`en-CA`,{timeZone:t,year:`numeric`,month:`2-digit`,day:`2-digit`}).format(e);if(Re.test(n))return n}catch{}return(/* @__PURE__ */ new Date(e.getTime()-e.getTimezoneOffset()*6e4)).toISOString().slice(0,10)}function Be(e,t){let n=M(e);return Number.isNaN(n.getTime())?e:new Intl.DateTimeFormat(t,{timeZone:`UTC`,weekday:`long`,day:`numeric`,month:`long`}).format(n)}function Ve(e,t){let n=N(t.today,t.daysAhead);return e.filter(e=>e.completed&&!t.showCompleted&&!t.keep?.has(e.uid)?!1:e.date<t.today?t.showPast:e.date<=n)}function He(e,t){return e<t?`past`:e===t?`today`:e===N(t,1)?`tomorrow`:`future`}function Ue(e,t){let n=e.last_partial;return t<100?n=t:e.progress<100&&(n=e.progress),{progress:t,completed:t>=100,last_partial:n}}function We(e){if(e.length===0)return 0;let t=e.reduce((e,t)=>e+t.progress,0);return Math.min(Math.max(Math.floor(t/e.length+.5),0),100)}function Ge(e){return e.derived===!0&&e.disabled!==!0&&(e.subtasks?.length??0)>0}function Ke(e,t){if(t.length===0)return{...e,subtasks:t,derived:!1};let n=We(t);return{...e,subtasks:t,derived:!0,progress:n,completed:n>=100}}function qe(e,t){return t.size===0?[...e]:e.map(e=>{let n=e.subtasks;if(n?.some(e=>t.has(e.uid)))return Ke(e,n.map(e=>{let n=t.get(e.uid);return n?{...e,...n}:e}));let r=t.get(e.uid);return r?{...e,...r}:e})}var Je=[15,30,45,60,90,120,180,240];function Ye(...e){let t=e.filter((t,n)=>typeof t==`number`&&!Je.includes(t)&&e.indexOf(t)===n);return[...Je,...t].sort((e,t)=>e-t)}function P(e,t){let n=t===`nl`?`u`:`h`,r=Math.max(0,Math.round(e)),i=Math.floor(r/60),a=r%60;return i===0?`${a} min`:a===0?`${i} ${n}`:`${i} ${n} ${a} min`}function Xe(e){let t=/* @__PURE__ */ new Map;for(let n of e)if(n.disabled!==!0)for(let e of n.subtasks??[])typeof e.minutes==`number`&&t.set(e.date,(t.get(e.date)??0)+e.minutes);return t}function Ze(e,t){let n=P(e,t);return Math.round(e)>=60?n.replace(/ min$/,``):n}function Qe(e){let t=M(e);return Number.isNaN(t.getTime())?-1:(t.getUTCDay()+6)%7}function $e(e){let t=e.daily_max_weekdays;return Array.isArray(t)&&t.length===7&&t.every(e=>Number.isFinite(e))?t:void 0}function et(e,t){if(!e)return{max:void 0,normal:void 0,adjusted:!1};let n=$e(e),r=Qe(t),i=(n&&r>=0?n[r]:void 0)??(typeof e.daily_max_minutes==`number`?e.daily_max_minutes:void 0),a=e.daily_max_overrides?.[t];return typeof a==`number`?{max:a,normal:i,adjusted:a!==i}:{max:i,normal:i,adjusted:!1}}function tt(e,t){return e.map(e=>{let n=t.get(e.id);return n?{...e,...n}:e})}var F=e=>e.status===`proposed`;function nt(e,t){let n;for(let r of e)F(r)&&r.kind===`period`&&r.start!==void 0&&r.end!==void 0&&typeof r.minutes==`number`&&(t<r.start||t>r.end||(n===void 0||r.minutes<n)&&(n=r.minutes));return n}function rt(e,t,n){let r=M(e),i=M(t);if(Number.isNaN(r.getTime())||Number.isNaN(i.getTime()))return`${e} – ${t}`;let a=e=>new Intl.DateTimeFormat(n,{timeZone:`UTC`,month:`short`}).format(e).replace(/\./g,``),o=`${r.getUTCDate()} ${a(r)}`,s=`${i.getUTCDate()} ${a(i)}`;return o===s&&e===t?o:r.getUTCMonth()===i.getUTCMonth()&&r.getUTCFullYear()===i.getUTCFullYear()?`${r.getUTCDate()}–${s}`:`${o} – ${s}`}function I(e){let t=e.indexOf(`:sub:`);return t<0?e:e.slice(0,t)}function it(e,t,n,r){if(e.completed)return e.date;let i=t<r?r:t;return i>n?n:i}function at(e,t,n){return t.size===0?[...e]:e.map(e=>{let r=e.subtasks;if(!r?.some(e=>t.has(e.uid)))return e;let i=[];for(let a of r){let r=t.get(a.uid);if(!r)i.push(a);else if(!r.deleted){let t=r.planned??a.planned;i.push({...a,title:r.title??a.title,planned:t,...r.minutes===void 0?{}:{minutes:r.minutes},date:it(a,t,e.date,n)})}}return Ke(e,i)})}function ot(e,t){return t.deleted?e===void 0:!e||(t.title===void 0||e.title===t.title)&&(t.planned===void 0||e.planned===t.planned)&&(t.minutes===void 0||(e.minutes??null)===t.minutes)}var st=`overdue`;function ct(e,t){let n=N(t.today,t.daysAhead),r=/* @__PURE__ */ new Map,i=(e,n)=>{let i=r.get(e);i||(i={date:e,kind:e===`overdue`?`overdue`:He(e,t.today),entries:[]},r.set(e,i)),i.entries.push(n)};for(let n of Ve(e,t))i(n.date,{type:`item`,item:n});let a=[];for(let r of e)if(r.disabled!==!0)for(let e of r.subtasks??[]){if(e.completed&&!t.showCompleted&&!t.keep?.has(e.uid))continue;let i=t.keep?.has(e.uid)===!0&&r.date<t.today;e.overdue||i?a.push([st,{type:`subtask`,subtask:e,parent:r}]):(e.date<t.today?!t.showPast:e.date>n)||a.push([e.date,{type:`subtask`,subtask:e,parent:r}])}for(let[e,t]of a)i(e,t);return[...r.values()].sort((e,t)=>e.kind===`overdue`||t.kind===`overdue`?e.kind===t.kind?0:e.kind===`overdue`?-1:1:e.date.localeCompare(t.date))}function L(e,t){let n=M(e);return Number.isNaN(n.getTime())?e:new Intl.DateTimeFormat(t,{timeZone:`UTC`,weekday:`short`,day:`numeric`,month:`short`}).format(n).replace(/\./g,``)}var R=[{period:`next_day`,option:`show_progress_tomorrow`},{period:`week`,option:`show_progress_week`},{period:`next_week`,option:`show_progress_next_week`}];function lt(e){let t=Number.isFinite(e.value)?e.value:0;return Math.min(Math.max(Math.round(t),0),100)}function ut(e){if(!e||typeof e!=`object`)throw Error(`Invalid configuration`);let t=e.entity??``;if(typeof t!=`string`)throw Error(`entity must be a to-do entity id`);if(t!==``&&!t.startsWith(`todo.`))throw Error(`entity must be a to-do entity (todo.*)`);let n=e.days_ahead??7;if(typeof n!=`number`||!Number.isFinite(n)||n<0)throw Error(`days_ahead must be a number of days (0 or more)`);return{entity:t,show_completed:e.show_completed===!0,show_past:e.show_past===!0,days_ahead:Math.min(Math.floor(n),365),show_progress_tomorrow:e.show_progress_tomorrow===!0,show_progress_week:e.show_progress_week===!0,show_progress_next_week:e.show_progress_next_week===!0,title:typeof e.title==`string`?e.title:``,language:e.language===`nl`||e.language===`en`?e.language:`auto`,card_id:typeof e.card_id==`string`?e.card_id:``}}function z(e,t){return`${e}\u0000${t}`}function dt(e,t){if(t.size===0)return[...e];let n=[];for(let r of e){let e=r.manual_labels.filter(e=>!t.has(z(r.uid,e.id)));if(e.length===r.manual_labels.length)n.push(r);else if(r.info_type!==null||e.length>0){let t=e.length===0&&r.override?.mode===`disable`;n.push({...r,manual_labels:e,...t?{disabled:!0,completed:!0,is_test:!1}:{}})}}return n}function ft(e,t,n){let r=N(t,Math.max(n,21));for(let t of e)t.date>r&&(r=t.date);return{min:t,max:r}}function pt(e){return/T(\d{2}:\d{2})/.exec(e)?.[1]??``}function mt(e){if(e.all_day)return``;let t=pt(e.start),n=pt(e.end);return t&&n?`${t}\u2013${n}`:t}function ht(e){let t=2166136261;for(let n=0;n<e.length;n++)t^=e.charCodeAt(n),t=Math.imul(t,16777619)>>>0;return t.toString(16).padStart(8,`0`)}function gt(){try{return[...crypto.getRandomValues(/* @__PURE__ */ new Uint8Array(6))].map(e=>e.toString(16).padStart(2,`0`)).join(``)}catch{return Math.random().toString(36).slice(2,14).padEnd(12,`0`)}}function _t(e){let t=e.card_id||ht(`${e.entity}\u0000${e.title}`),n=ht(JSON.stringify([e.entity,e.title,e.card_id,e.language,e.show_completed,e.show_past,e.days_ahead,e.show_progress_tomorrow,e.show_progress_week,e.show_progress_next_week]));return`magister-homework-card:${e.entity}:${t}:${n}`}function vt(e){try{let t=window.localStorage.getItem(e);if(t===null)return;let n=JSON.parse(t);if(typeof n?.show_completed==`boolean`&&typeof n.show_past==`boolean`)return{show_completed:n.show_completed,show_past:n.show_past}}catch{}}function yt(e,t){try{window.localStorage.setItem(e,JSON.stringify(t))}catch{return}try{let t=e.slice(0,e.lastIndexOf(`:`)+1),n=[];for(let r=0;r<window.localStorage.length;r++){let i=window.localStorage.key(r);i!==null&&i!==e&&i.startsWith(t)&&n.push(i)}for(let e of n)window.localStorage.removeItem(e)}catch{}}var bt={1:`default_homework`,2:`default_test`,3:`default_exam`,4:`default_written_quiz`,5:`default_oral_quiz`};function xt(e,t){let n=e.manual_labels.some(e=>e.kind===`test`);switch(t.mode){case`replace`:return{override:{mode:`replace`,label:t.label},disabled:!1,is_test:t.label.kind===`test`||n};case`disable`:return{override:{mode:`disable`},disabled:e.manual_labels.length===0,is_test:n};case`clear`:return{override:null,disabled:!1,is_test:e.info_type!==null&&e.info_type>=2||n}}}function St(e){return{override:e.override??null,disabled:e.disabled===!0,is_test:e.is_test}}function Ct(e,t){return!e||!t?!e&&!t:e.mode===t.mode?e.mode===`replace`&&t.mode===`replace`?e.label.id===t.label.id:!0:!1}function wt(e,t){return Ct(e.override,t.override)&&e.disabled===!0==(t.disabled===!0)&&e.is_test===t.is_test}function Tt(e,t){return t.size===0?[...e]:e.map(e=>{let n=t.get(e.uid);return n?{...e,...n,completed:e.progress>=100||n.disabled===!0}:e})}function Et(e,t){let n=e.info_type===null?void 0:bt[e.info_type],r=e.override?.mode===`replace`?e.override.label.id:void 0;return{replace:e.disabled===!0?[]:t.filter(e=>e.id!==n&&e.id!==r),disable:e.disabled!==!0&&e.override?.mode!==`disable`,restore:e.override!=null}}var Dt={nl:{today:`Vandaag`,tomorrow:`Morgen`,earlier:`Eerder`,no_homework:`Geen huiswerk 🎉`,loading:`Laden…`,unavailable:`Magister is niet beschikbaar. Je ziet het laatst bekende huiswerk; wijzigen kan nu niet.`,offline:`Verbinding met Home Assistant verbroken. Opnieuw verbinden…`,choose_entity:`Kies een Magister-huiswerklijst in de kaartinstellingen.`,not_found:`Deze huiswerklijst is niet gevonden.`,unauthorized:`Je hebt geen toegang tot deze huiswerklijst.`,load_failed:`Het huiswerk kon niet worden geladen.`,save_failed:`Opslaan mislukt. De wijziging is teruggedraaid.`,save_unauthorized:`Geen rechten om voortgang te wijzigen.`,dismiss:`Sluiten`,cancelled:`Les vervallen`,attachments:`Bijlagen in Magister`,lesson_hour:`Uur {n}`,mark_done:`Markeer {subject} als klaar`,mark_open:`Markeer {subject} als niet klaar`,progress_of:`Voortgang van {subject}`,percent:`{n} %`,expand:`Toon de volledige tekst`,collapse:`Toon minder`,progress_label:{next_day:`Volgende schooldag`,week:`Deze week`,next_week:`Volgende week`},progress_done:`{completed} van {items} klaar`,progress_empty:`geen huiswerk`,progress_unavailable:`niet beschikbaar`,switches_label:`Weergave`,show_completed_switch:`Afgerond`,show_completed_tip:`Toon afgerond huiswerk`,show_past_switch:`Eerder`,show_past_tip:`Toon eerdere dagen`,add_label:`Label toevoegen`,remove_label:`Label {name} verwijderen`,confirm_remove:`Label {name} verwijderen?`,confirm_yes:`Verwijderen`,confirm_no:`Annuleren`,override_menu:`Magister-label van {subject} wijzigen`,override_tip:`Magister-label wijzigen`,override_replace_with:`Vervangen door…`,override_replace_option:`Vervangen door {name}`,override_disable:`Uitschakelen`,override_restore:`Herstellen`,override_replaced:`vervangen`,override_disabled:`uitgeschakeld`,sub:{add:`+ deelstap`,add_aria:`Deelstap toevoegen aan {subject}`,form_add:`Deelstap toevoegen aan {subject}`,form_edit:`Deelstap {title} bewerken`,title:`Titel`,date:`Dag`,date_fixed:`Dag (de dag van de les)`,save:`Opslaan`,saving:`Opslaan…`,cancel:`Annuleren`,edit:`Bewerken`,edit_aria:`Deelstap {title} bewerken`,delete:`Verwijderen`,delete_aria:`Deelstap {title} verwijderen`,confirm_delete:`Deelstap {title} verwijderen?`,confirm_yes:`Verwijderen`,for_item:`voor {label} {subject} ({date})`,overdue:`Achterstallig`,ai:`AI`,ai_label:`Aangemaakt door AI-coach`,parent:`Ouder`,parent_label:`Aangemaakt door ouder via AI`,minutes:`Geschatte tijd`,minutes_none:`—`,planned:`± {time} gepland`,over_max:`boven dagmaximum ({max})`,max_short:`/ max {max}`,adjusted_max:`aangepast dagmaximum ({max})`,over_adjusted_max:`boven aangepast dagmaximum ({max})`,max_short_adjusted:`/ max {max} (aangepast)`,overdue_group:`Achterstallig`,marker:`{n} deelstappen`,marker_one:`{n} deelstap`,marker_aria:`heeft {n} deelstappen`,marker_aria_one:`heeft {n} deelstap`,over_zero_max:`geen studietijd ingesteld voor deze dag ({max})`,over_zero_adjusted_max:`geen studietijd ingesteld voor deze dag, aangepast dagmaximum ({max})`,count:`{done} van {total} deelstappen`,count_one:`{done} van {total} deelstap`,derived_check:`Voortgang van {subject} volgt uit de deelstappen`,derived_hint:`Voortgang volgt uit de deelstappen`,derived_value:`{count}, {n} %`,mark_done:`Markeer deelstap {title} als klaar`,mark_open:`Markeer deelstap {title} als niet klaar`,progress_of:`Voortgang van deelstap {title}`,errors:{invalid_format:`Vul een titel in van 1 tot 100 tekens.`,invalid_date:`Kies een dag vanaf vandaag tot en met de dag van de les.`,invalid_minutes:`Kies een geschatte tijd uit de lijst.`,item_has_subtasks:`De voortgang van dit item volgt uit zijn deelstappen.`,too_many_subtasks:`Een item kan maximaal 20 deelstappen hebben.`,item_disabled:`Dit item is uitgeschakeld. Herstel eerst het Magister-label.`,item_not_found:`Dit item is niet meer gevonden.`,subtask_not_found:`Deze deelstap is niet meer gevonden.`,unauthorized:`Je hebt geen rechten om deelstappen te wijzigen.`,not_found:`Deze huiswerklijst is niet gevonden.`,default:`Opslaan mislukt.`}},proposal:{title:`Voorstel van de coach`,period:`{reason} {range}, max {max} per dag`,weekdays:`{reason}, max per dag: {values}`,none:`geen`,weekdays_short:[`ma`,`di`,`wo`,`do`,`vr`,`za`,`zo`],expires:`Verloopt op {date}`,answer_by:`Beantwoorden kan t/m {date}`,accept:`Accepteren`,reject:`Afwijzen`,accept_aria:`Voorstel accepteren: {summary}`,reject_aria:`Voorstel afwijzen: {summary}`,group_aria:`Voorstel van de coach: {summary}`,confirm:`Dit voorstel accepteren? Het geldt direct.`,confirm_yes:`Accepteren`,confirm_no:`Annuleren`,day_note:`voorstel: max {max}`,day_note_aria:`voorstel, nog niet geaccepteerd: max {max}`,earlier:`Eerdere voorstellen`,accepted:`geaccepteerd`,rejected:`afgewezen`,expired:`verlopen`,on_behalf:`namens het kind`,closed_on:`{status} op {date}`,accepted_toast:`Voorstel geaccepteerd.`,rejected_toast:`Voorstel afgewezen.`,errors:{not_allowed_for_role:`Alleen de leerling (of, als het kind geen eigen account heeft, een ouder) kan dit voorstel beantwoorden.`,proposal_closed:`Dit voorstel is al beantwoord of verlopen.`,too_many_notes:`Het voorstel kan niet worden geaccepteerd: er zijn al 50 notities voor dit kind. Verwijder eerst een notitie.`,proposal_not_found:`Dit voorstel bestaat niet meer.`,unauthorized:`Je hebt geen rechten om voorstellen te beantwoorden.`,not_found:`Deze huiswerklijst is niet gevonden.`,default:`Antwoorden mislukt. De wijziging is teruggedraaid.`}},kind:{homework:`huiswerk`,test:`toets`},all_day:`Hele dag`,dialog:{title:`Label toevoegen`,date:`Dag`,lessons:`Les`,lessons_loading:`Lessen laden…`,no_lessons:`Geen lessen op deze dag.`,label:`Label`,choose_label:`Kies een label`,note:`Notitie (optioneel)`,note_count:`{n} van 200 tekens`,save:`Opslaan`,saving:`Opslaan…`,cancel:`Annuleren`,close:`Sluiten`},label_errors:{unauthorized:`Je hebt geen rechten om labels te wijzigen.`,not_found:`Deze huiswerklijst is niet gevonden.`,invalid_format:`Ongeldige invoer.`,invalid_date:`Deze dag valt buiten de opgehaalde periode.`,appointment_not_found:`Deze les is niet meer gevonden. Kies de dag opnieuw.`,label_not_found:`Dit label bestaat niet meer. Kies een ander label.`,label_exists:`Deze les heeft dit label al.`,label_not_on_appointment:`Dit label staat niet meer op de les.`,no_magister_label:`Deze les heeft geen Magister-label om te wijzigen.`,item_disabled:`Dit item is uitgeschakeld. Herstel eerst het Magister-label.`,default:`Opslaan mislukt.`,load_default:`De lessen konden niet worden geladen.`},type:{1:`Huiswerk`,2:`Proefwerk`,3:`Tentamen`,4:`SO`,5:`MO`},timer:{region:`Studietimer`,start:`Timer starten`,start_aria:`Timer starten voor {title} ({time})`,pause:`Pauze`,pause_aria:`Timer van {title} pauzeren`,resume:`Hervat`,resume_aria:`Timer van {title} hervatten`,stop:`Stop`,stop_aria:`Timer van {title} stoppen`,running:`Loopt`,paused:`Gepauzeerd`,finished:`Tijd is om`,done:`Klaar`,done_aria:`{title} is klaar`,extra:`+{n} min`,extra_aria:`{n} extra minuten voor {title}`,not_yet:`Nog niet`,not_yet_aria:`{title} is nog niet klaar`,countdown_aria:`{title}: {state}`,meta:`{subject} · {label} · {date}`,confirm_replace:`Er loopt al een timer voor {title}. Die stoppen en deze starten?`,confirm_yes:`Vervangen`,confirm_no:`Annuleren`,confirm_no_aria:`Timer van {title} niet starten`,finished_group:`Tijd is om: {title}`,panel_title:`Hoe ver ben je?`,panel_aria:`Voortgang van {title}`,panel_steps:`Voortgang in procenten`,panel_save:`Opslaan en stoppen`,panel_discard:`Stoppen zonder voortgang`,panel_cancel:`Annuleren`,settings:`Timerinstellingen`,settings_title:`Timerinstellingen`,prewarn:`Waarschuwing vooraf`,extra_minutes:`Extra minuten`,off:`Uit`,minutes_option:`{n} min`,save:`Opslaan`,cancel:`Annuleren`,settings_hint:`De melding vooraf komt zoveel minuten voor het einde. Extra minuten kun je erbij nemen als de tijd om is.`,idle:`Geen timer actief`,read_only:`Alleen de leerling bedient de timer. Je kunt hem hier wel volgen.`,announce_prewarn:`Nog {n} minuten: {title}`,announce_prewarn_one:`Nog 1 minuut: {title}`,announce_end:`Tijd is om: {title}`,language:`nl`,notify_prewarn:`Nog {n} minuten: {what}`,notify_prewarn_one:`Nog 1 minuut: {what}`,notify_end:`Tijd is om: {what}`,notify_title:`Meldingen`,notify_confirm:`Meldingen staan aan`,notify_enable:`Meldingen in deze browser`,notify_sound:`Geluid`,notify_hint:`Een melding komt alleen zolang deze pagina open staat (een ander tabblad mag). De keuze geldt alleen voor deze browser.`,notify_denied:`Je browser staat meldingen niet toe`,notify_denied_hint:`Sta meldingen voor deze site toe in de instellingen van je browser (bij het slotje naast het adres) en zet ze daarna opnieuw aan.`,notify_unsupported:`Deze browser ondersteunt geen meldingen.`,notify_insecure:`Meldingen werken alleen op een beveiligde verbinding (https).`,notify_app:`Gebruik de meldingen van de app.`,errors:{no_minutes:`Deze deelstap heeft geen geschatte tijd, dus er kan geen timer op.`,subtask_not_found:`Deze deelstap is niet meer gevonden.`,subtask_completed:`Deze deelstap is al afgerond.`,no_timer:`Er is geen timer meer: hij is al gestopt.`,timer_running:`Er loopt al een timer. Stop die eerst.`,timer_wrong_state:`De timer staat nu anders. Kijk naar de timer en probeer het opnieuw.`,timer_not_finished:`Extra tijd kan pas als de timer is afgelopen.`,extra_not_set:`Je hebt geen extra minuten ingesteld (Timerinstellingen).`,not_allowed_for_role:`Alleen de leerling bedient de timer. Een ouder of beheerder mag dat alleen als het kind geen eigen account heeft.`,not_found:`Deze huiswerklijst is niet gevonden.`,invalid_format:`Ongeldige invoer. Kies waarden uit de lijst.`,unauthorized:`Je hebt geen rechten om de timer te bedienen.`,default:`De timer kon niet worden bijgewerkt. De wijziging is teruggedraaid.`}},editor:{entity:`Huiswerklijst (to-do van een kind)`,title:`Titel (optioneel)`,language:`Taal van de kaart`,language_auto:`Automatisch (taal van Home Assistant)`,show_completed:`Toon afgerond huiswerk`,show_past:`Toon eerdere dagen`,days_ahead:`Dagen vooruit`,show_progress_tomorrow:`Toon voortgang volgende schooldag`,show_progress_week:`Toon voortgang van deze week`,show_progress_next_week:`Toon voortgang van volgende week`,show_when_idle:`Toon de kaart ook zonder actieve timer`}},en:{today:`Today`,tomorrow:`Tomorrow`,earlier:`Earlier`,no_homework:`No homework`,loading:`Loading…`,unavailable:`Magister is not available. You see the last known homework; changes are not possible now.`,offline:`Connection to Home Assistant lost. Reconnecting…`,choose_entity:`Choose a Magister homework list in the card settings.`,not_found:`This homework list was not found.`,unauthorized:`You have no access to this homework list.`,load_failed:`The homework could not be loaded.`,save_failed:`Saving failed. The change was rolled back.`,save_unauthorized:`No permission to change progress.`,dismiss:`Dismiss`,cancelled:`Lesson cancelled`,attachments:`Attachments in Magister`,lesson_hour:`Period {n}`,mark_done:`Mark {subject} as done`,mark_open:`Mark {subject} as not done`,progress_of:`Progress of {subject}`,percent:`{n}%`,expand:`Show the full text`,collapse:`Show less`,progress_label:{next_day:`Next school day`,week:`This week`,next_week:`Next week`},progress_done:`{completed} of {items} done`,progress_empty:`no homework`,progress_unavailable:`not available`,switches_label:`View`,show_completed_switch:`Done`,show_completed_tip:`Show completed homework`,show_past_switch:`Earlier`,show_past_tip:`Show earlier days`,add_label:`Add label`,remove_label:`Remove label {name}`,confirm_remove:`Remove label {name}?`,confirm_yes:`Remove`,confirm_no:`Cancel`,override_menu:`Change the Magister label of {subject}`,override_tip:`Change the Magister label`,override_replace_with:`Replace with…`,override_replace_option:`Replace with {name}`,override_disable:`Disable`,override_restore:`Restore`,override_replaced:`replaced`,override_disabled:`disabled`,sub:{add:`+ subtask`,add_aria:`Add a subtask to {subject}`,form_add:`Add a subtask to {subject}`,form_edit:`Edit subtask {title}`,title:`Title`,date:`Day`,date_fixed:`Day (the day of the lesson)`,save:`Save`,saving:`Saving…`,cancel:`Cancel`,edit:`Edit`,edit_aria:`Edit subtask {title}`,delete:`Delete`,delete_aria:`Delete subtask {title}`,confirm_delete:`Delete subtask {title}?`,confirm_yes:`Delete`,for_item:`for {label} {subject} ({date})`,overdue:`Overdue`,ai:`AI`,ai_label:`Created by AI coach`,parent:`Parent`,parent_label:`Created by parent via AI`,minutes:`Estimated time`,minutes_none:`—`,planned:`± {time} planned`,over_max:`over daily maximum ({max})`,max_short:`/ max {max}`,adjusted_max:`adjusted daily maximum ({max})`,over_adjusted_max:`over adjusted daily maximum ({max})`,max_short_adjusted:`/ max {max} (adjusted)`,overdue_group:`Overdue`,marker:`{n} subtasks`,marker_one:`{n} subtask`,marker_aria:`has {n} subtasks`,marker_aria_one:`has {n} subtask`,over_zero_max:`no study time set for this day ({max})`,over_zero_adjusted_max:`no study time set for this day, adjusted daily maximum ({max})`,count:`{done} of {total} subtasks`,count_one:`{done} of {total} subtask`,derived_check:`Progress of {subject} follows from the subtasks`,derived_hint:`Progress follows from the subtasks`,derived_value:`{count}, {n}%`,mark_done:`Mark subtask {title} as done`,mark_open:`Mark subtask {title} as not done`,progress_of:`Progress of subtask {title}`,errors:{invalid_format:`Enter a title of 1 to 100 characters.`,invalid_date:`Choose a day from today up to and including the day of the lesson.`,invalid_minutes:`Choose an estimated time from the list.`,item_has_subtasks:`This item's progress follows from its subtasks.`,too_many_subtasks:`An item can have at most 20 subtasks.`,item_disabled:`This item is disabled. Restore the Magister label first.`,item_not_found:`This item was not found any more.`,subtask_not_found:`This subtask was not found any more.`,unauthorized:`You have no permission to change subtasks.`,not_found:`This homework list was not found.`,default:`Saving failed.`}},proposal:{title:`Proposal from the coach`,period:`{reason} {range}, max {max} per day`,weekdays:`{reason}, max per day: {values}`,none:`none`,weekdays_short:[`Mon`,`Tue`,`Wed`,`Thu`,`Fri`,`Sat`,`Sun`],expires:`Expires on {date}`,answer_by:`Answer by {date}`,accept:`Accept`,reject:`Reject`,accept_aria:`Accept proposal: {summary}`,reject_aria:`Reject proposal: {summary}`,group_aria:`Proposal from the coach: {summary}`,confirm:`Accept this proposal? It applies at once.`,confirm_yes:`Accept`,confirm_no:`Cancel`,day_note:`proposal: max {max}`,day_note_aria:`proposal, not accepted yet: max {max}`,earlier:`Earlier proposals`,accepted:`accepted`,rejected:`rejected`,expired:`expired`,on_behalf:`on behalf of the child`,closed_on:`{status} on {date}`,accepted_toast:`Proposal accepted.`,rejected_toast:`Proposal rejected.`,errors:{not_allowed_for_role:`Only the student (or, for a child without their own account, a parent) can answer this proposal.`,proposal_closed:`This proposal has already been answered or has expired.`,too_many_notes:`The proposal cannot be accepted: there are already 50 notes for this child. Delete a note first.`,proposal_not_found:`This proposal no longer exists.`,unauthorized:`You have no permission to answer proposals.`,not_found:`This homework list was not found.`,default:`Answering failed. The change was rolled back.`}},kind:{homework:`homework`,test:`test`},all_day:`All day`,dialog:{title:`Add label`,date:`Day`,lessons:`Lesson`,lessons_loading:`Loading lessons…`,no_lessons:`No lessons on this day.`,label:`Label`,choose_label:`Choose a label`,note:`Note (optional)`,note_count:`{n} of 200 characters`,save:`Save`,saving:`Saving…`,cancel:`Cancel`,close:`Close`},label_errors:{unauthorized:`You have no permission to change labels.`,not_found:`This homework list was not found.`,invalid_format:`Invalid input.`,invalid_date:`This day is outside the fetched period.`,appointment_not_found:`This lesson was not found any more. Choose the day again.`,label_not_found:`This label no longer exists. Choose another label.`,label_exists:`This lesson already has this label.`,label_not_on_appointment:`This label is no longer on the lesson.`,no_magister_label:`This lesson has no Magister label to change.`,item_disabled:`This item is disabled. Restore the Magister label first.`,default:`Saving failed.`,load_default:`The lessons could not be loaded.`},type:{1:`Homework`,2:`Test`,3:`Exam`,4:`Short test`,5:`Oral test`},timer:{region:`Study timer`,start:`Start timer`,start_aria:`Start timer for {title} ({time})`,pause:`Pause`,pause_aria:`Pause the timer of {title}`,resume:`Resume`,resume_aria:`Resume the timer of {title}`,stop:`Stop`,stop_aria:`Stop the timer of {title}`,running:`Running`,paused:`Paused`,finished:`Time is up`,done:`Done`,done_aria:`{title} is done`,extra:`+{n} min`,extra_aria:`{n} extra minutes for {title}`,not_yet:`Not yet`,not_yet_aria:`{title} is not done yet`,countdown_aria:`{title}: {state}`,meta:`{subject} · {label} · {date}`,confirm_replace:`A timer is already running for {title}. Stop it and start this one?`,confirm_yes:`Replace`,confirm_no:`Cancel`,confirm_no_aria:`Do not start the timer for {title}`,finished_group:`Time is up: {title}`,panel_title:`How far are you?`,panel_aria:`Progress of {title}`,panel_steps:`Progress in percent`,panel_save:`Save and stop`,panel_discard:`Stop without progress`,panel_cancel:`Cancel`,settings:`Timer settings`,settings_title:`Timer settings`,prewarn:`Warning beforehand`,extra_minutes:`Extra minutes`,off:`Off`,minutes_option:`{n} min`,save:`Save`,cancel:`Cancel`,settings_hint:`The warning comes this many minutes before the end. You can add extra minutes when time is up.`,idle:`No timer active`,read_only:`Only the student controls the timer. You can follow it here.`,announce_prewarn:`{n} minutes left: {title}`,announce_prewarn_one:`1 minute left: {title}`,announce_end:`Time is up: {title}`,language:`en`,notify_prewarn:`{n} minutes left: {what}`,notify_prewarn_one:`1 minute left: {what}`,notify_end:`Time is up: {what}`,notify_title:`Notifications`,notify_confirm:`Notifications are on`,notify_enable:`Notifications in this browser`,notify_sound:`Sound`,notify_hint:`A notification only appears while this page is open (another tab is fine). The choice applies to this browser only.`,notify_denied:`Your browser does not allow notifications`,notify_denied_hint:`Allow notifications for this site in your browser settings (the padlock next to the address) and switch them on again.`,notify_unsupported:`This browser does not support notifications.`,notify_insecure:`Notifications only work on a secure connection (https).`,notify_app:`Use the notifications of the app.`,errors:{no_minutes:`This subtask has no estimated time, so it cannot get a timer.`,subtask_not_found:`This subtask no longer exists.`,subtask_completed:`This subtask is already completed.`,no_timer:`There is no timer any more: it has already stopped.`,timer_running:`A timer is already running. Stop it first.`,timer_wrong_state:`The timer is in another state now. Look at the timer and try again.`,timer_not_finished:`Extra time can only be added when the timer has run out.`,extra_not_set:`You have not set extra minutes (Timer settings).`,not_allowed_for_role:`Only the student controls the timer. A parent or an administrator may only do so when the child has no account of their own.`,not_found:`This homework list was not found.`,invalid_format:`Invalid input. Choose values from the list.`,unauthorized:`You have no permission to control the timer.`,default:`The timer could not be updated. The change was rolled back.`}},editor:{entity:`Homework list (a child's to-do)`,title:`Title (optional)`,language:`Card language`,language_auto:`Automatic (Home Assistant language)`,show_completed:`Show completed homework`,show_past:`Show earlier days`,days_ahead:`Days ahead`,show_progress_tomorrow:`Show next school day progress`,show_progress_week:`Show progress for this week`,show_progress_next_week:`Show progress for next week`,show_when_idle:`Show the card when no timer is active`}}};function Ot(e,t){return e===`nl`||e===`en`?e:kt(t)}function kt(e){return e?.toLowerCase().startsWith(`nl`)?`nl`:`en`}function B(e){return Dt[kt(e)]}function V(e,t){return e.replace(/\{(\w+)\}/g,(e,n)=>n in t?String(t[n]):e)}function At(e,t,n){return e.type[t]??n}function jt(e=B(`en`)){return[{name:`entity`,required:!0,selector:{entity:{filter:{domain:`todo`,integration:`magister`}}}},{name:`title`,selector:{text:{}}},{name:`language`,selector:{select:{mode:`dropdown`,options:[{value:`auto`,label:e.editor.language_auto},{value:`nl`,label:`Nederlands`},{value:`en`,label:`English`}]}}},{name:`show_completed`,selector:{boolean:{}}},{name:`show_past`,selector:{boolean:{}}},{name:`days_ahead`,selector:{number:{min:0,max:365,step:1,mode:`box`}}},...R.map(({option:e})=>({name:e,selector:{boolean:{}}}))]}function Mt(e){return{entity:e.entity??``,title:e.title??``,language:e.language??`auto`,show_completed:e.show_completed??!1,show_past:e.show_past??!1,days_ahead:e.days_ahead??7,show_progress_tomorrow:e.show_progress_tomorrow??!1,show_progress_week:e.show_progress_week??!1,show_progress_next_week:e.show_progress_next_week??!1}}function Nt(e,t){let n={...e,type:e.type??`custom:magister-homework-card`,entity:typeof t.entity==`string`?t.entity:e.entity??``},r=t.title;typeof r==`string`&&r.trim()!==``?n.title=r:delete n.title;let i=t.language;i===`nl`||i===`en`?n.language=i:delete n.language,t.show_completed===!0?n.show_completed=!0:delete n.show_completed,t.show_past===!0?n.show_past=!0:delete n.show_past;let a=n;for(let{option:e}of R)t[e]===!0?a[e]=!0:delete a[e];let o=t.days_ahead,s=o===``||o==null?NaN:Number(o);return Number.isFinite(s)&&s>=0&&s!==7?n.days_ahead=Math.min(Math.floor(s),365):delete n.days_ahead,n}var Pt=class extends A{constructor(...e){super(...e),this._computeLabel=e=>this._texts().editor[e.name]??e.name,this._valueChanged=e=>{if(e.stopPropagation(),!this._config)return;let t=Nt(this._config,e.detail.value);t.card_id??=gt(),this._config=t,this.dispatchEvent(new CustomEvent(`config-changed`,{detail:{config:t},bubbles:!0,composed:!0}))}}static{this.properties={hass:{attribute:!1},_config:{state:!0}}}setConfig(e){this._config=e}_texts(){return B(this.hass?.locale?.language??this.hass?.language)}render(){return this._config?C`<ha-form
      .hass=${this.hass}
      .data=${Mt(this._config)}
      .schema=${jt(this._texts())}
      .computeLabel=${this._computeLabel}
      @value-changed=${this._valueChanged}
    ></ha-form>`:T}},Ft=`magister/homework/appointments`,It=`magister/homework/add_label`,Lt=class extends A{static{this.properties={hass:{attribute:!1},entity:{attribute:!1},labels:{attribute:!1},texts:{attribute:!1},language:{attribute:!1},today:{attribute:!1},min:{attribute:!1},max:{attribute:!1},_date:{state:!0},_appointments:{state:!0},_loading:{state:!0},_loadError:{state:!0},_selected:{state:!0},_label:{state:!0},_note:{state:!0},_saving:{state:!0},_error:{state:!0}}}constructor(){super(),this._request=0,this._closedSent=!1,this._date=``,this._appointments=[],this._loading=!1,this._loadError=``,this._selected=``,this._label=``,this._note=``,this._saving=!1,this._error=``}connectedCallback(){super.connectedCallback(),this._date=this.today}firstUpdated(){let e=this._dialog();e&&(typeof e.showModal==`function`?e.showModal():e.setAttribute(`open`,``)),this._load(this._date)}disconnectedCallback(){super.disconnectedCallback(),this._request++}_dialog(){return this.renderRoot.querySelector(`dialog`)}_close(){let e=this._dialog();e?.open&&e.close(),this._emitClosed()}_emitClosed(){this._closedSent||(this._closedSent=!0,this.dispatchEvent(new CustomEvent(`dialog-closed`,{bubbles:!0,composed:!0})))}async _load(e){let t=this.hass,n=++this._request;if(this._appointments=[],this._selected=``,this._loadError=``,this._error=``,!t||!e)this._loading=!1;else{this._loading=!0;try{let r=await t.callWS({type:Ft,entity_id:this.entity,date:e});if(n!==this._request)return;this._appointments=r.appointments}catch(e){if(n!==this._request)return;this._loadError=this._message(e,this.texts.label_errors.load_default??``)}finally{n===this._request&&(this._loading=!1)}}}_message(e,t){let n=e?.code;return(n?this.texts.label_errors[n]:void 0)??t}async _save(){let e=this.hass;if(!e||this._saving||!this._selected||!this._label)return;let t={type:It,entity_id:this.entity,appointment:this._selected,label:this._label},n=this._note.trim();n&&(t.note=n),this._saving=!0,this._error=``;try{await e.callWS(t),this._saving=!1,this.dispatchEvent(new CustomEvent(`label-added`,{bubbles:!0,composed:!0})),this._close()}catch(e){this._saving=!1,this._error=this._message(e,this.texts.label_errors.default??``)}}_describe(e){let t=this.texts,n=[];e.info_type!==null&&n.push(At(t,e.info_type,``));for(let t of e.manual_labels)n.push(t.name);return n.filter(Boolean).join(`, `)}render(){let e=this.texts,t=e.dialog,n=!this._saving&&this._selected!==``&&this._label!==``;return C`<dialog
      aria-labelledby="title"
      @close=${()=>{this._emitClosed()}}
      @cancel=${e=>{e.preventDefault(),this._close()}}
    >
      <form
        @submit=${e=>{e.preventDefault(),this._save()}}
      >
        <header>
          <h2 id="title">${t.title}</h2>
          <button type="button" class="close" aria-label=${t.close} @click=${()=>{this._close()}}>×</button>
        </header>

        <label class="field">
          <span>${t.date}</span>
          <input
            type="date"
            autofocus
            .value=${this._date}
            min=${this.min}
            max=${this.max}
            required
            @change=${e=>{this._date=e.target.value,this._load(this._date)}}
          />
          ${this._date?C`<small>${Be(this._date,this.language===`nl`?`nl`:`en-GB`)}</small>`:T}
        </label>

        <fieldset class="lessons" aria-busy=${this._loading?`true`:`false`}>
          <legend>${t.lessons}</legend>
          ${this._renderLessons()}
        </fieldset>

        <label class="field">
          <span>${t.label}</span>
          <select
            required
            @change=${e=>{this._label=e.target.value,this._error=``}}
          >
            <option value="" ?selected=${this._label===``}>${t.choose_label}</option>
            ${this.labels.map(t=>C`<option value=${t.id} ?selected=${this._label===t.id}>
                  ${t.name} (${e.kind[t.kind]})
                </option>`)}
          </select>
        </label>

        <label class="field">
          <span>${t.note}</span>
          <textarea
            rows="2"
            maxlength=${200}
            .value=${this._note}
            @input=${e=>{this._note=e.target.value}}
          ></textarea>
          <small class="count">${V(t.note_count,{n:this._note.length})}</small>
        </label>

        ${this._error?C`<p class="error" role="alert">${this._error}</p>`:T}

        <footer>
          <button type="button" class="secondary" @click=${()=>{this._close()}}>${t.cancel}</button>
          <button type="submit" class="primary" ?disabled=${!n}>
            ${this._saving?t.saving:t.save}
          </button>
        </footer>
      </form>
    </dialog>`}_renderLessons(){let e=this.texts;return this._loading?C`<p class="hint" role="status">${e.dialog.lessons_loading}</p>`:this._loadError?C`<p class="error" role="alert">${this._loadError}</p>`:this._appointments.length===0?C`<p class="hint" role="status">${e.dialog.no_lessons}</p>`:C`${this._appointments.map(t=>{let n=t.all_day?e.all_day:mt(t),r=this._describe(t);return C`<label class="lesson ${t.cancelled?`cancelled`:``}">
        <input
          type="radio"
          name="lesson"
          .value=${t.uid}
          .checked=${this._selected===t.uid}
          @change=${()=>{this._selected=t.uid,this._error=``}}
        />
        <span class="lesson-body">
          <span class="lesson-line">
            <strong>${t.subject}</strong>
            ${t.lesson_hour===null?T:C`<span class="meta">${V(e.lesson_hour,{n:t.lesson_hour})}</span>`}
            ${n?C`<span class="meta">${n}</span>`:T}
            ${t.cancelled?C`<span class="badge">${e.cancelled}</span>`:T}
          </span>
          ${r?C`<span class="lesson-labels">${r}</span>`:T}
        </span>
      </label>`})}`}static{this.styles=o`
    :host {
      display: contents;
    }
    dialog {
      box-sizing: border-box;
      width: min(480px, calc(100vw - 32px));
      max-height: calc(100vh - 32px);
      max-height: calc(100dvh - 32px);
      overflow: auto;
      padding: 16px;
      border: none;
      border-radius: 12px;
      background: var(--card-background-color, #fff);
      color: var(--primary-text-color, #212121);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
    }
    dialog::backdrop {
      background: rgba(0, 0, 0, 0.5);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    h2 {
      margin: 0;
      font-size: 1.2em;
      font-weight: 500;
    }
    .close {
      min-width: 44px;
      min-height: 44px;
      border: none;
      background: none;
      color: inherit;
      font-size: 1.6em;
      line-height: 1;
      cursor: pointer;
    }
    .field {
      display: flex;
      flex-direction: column;
      gap: 4px;
      margin: 12px 0;
      font-size: 0.9em;
      font-weight: 500;
    }
    .field small {
      font-weight: 400;
      color: var(--secondary-text-color);
    }
    input[type="date"],
    select,
    textarea {
      box-sizing: border-box;
      width: 100%;
      min-height: 44px;
      padding: 8px;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      background: var(--secondary-background-color, transparent);
      color: var(--primary-text-color);
      font: inherit;
      font-weight: 400;
    }
    textarea {
      resize: vertical;
    }
    fieldset.lessons {
      margin: 12px 0;
      padding: 0;
      border: none;
      min-width: 0;
    }
    legend {
      padding: 0;
      margin-bottom: 4px;
      font-size: 0.9em;
      font-weight: 500;
    }
    .lesson {
      display: flex;
      gap: 10px;
      align-items: flex-start;
      min-height: 44px;
      padding: 8px;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      margin-bottom: 6px;
      cursor: pointer;
    }
    .lesson:has(input:checked) {
      border-color: var(--primary-color);
      background: color-mix(in srgb, var(--primary-color) 12%, transparent);
    }
    .lesson input {
      flex: none;
      width: 20px;
      height: 20px;
      margin: 2px 0 0;
      accent-color: var(--primary-color);
    }
    .lesson.cancelled strong {
      text-decoration: line-through;
    }
    .lesson-body {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
    }
    .lesson-line {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 2px 8px;
    }
    .meta,
    .lesson-labels {
      font-size: 0.85em;
      color: var(--secondary-text-color);
    }
    .badge {
      padding: 0 8px;
      border-radius: 10px;
      font-size: 0.75em;
      color: var(--error-color);
      border: 1px solid var(--error-color);
    }
    .hint {
      margin: 8px 0;
      color: var(--secondary-text-color);
    }
    .error {
      margin: 8px 0;
      color: var(--error-color);
    }
    footer {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 16px;
    }
    footer button {
      min-height: 44px;
      padding: 0 16px;
      border-radius: 8px;
      font: inherit;
      font-weight: 500;
      cursor: pointer;
    }
    .secondary {
      border: 1px solid var(--divider-color);
      background: none;
      color: var(--primary-text-color);
    }
    .primary {
      border: 1px solid var(--primary-color);
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    .primary:disabled {
      opacity: 0.5;
      cursor: default;
    }
    input:focus-visible,
    select:focus-visible,
    textarea:focus-visible,
    button:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
  `}},Rt=`magister/homework/subscribe`,zt=3e4,Bt=6e5;function Vt(e){try{Promise.resolve(e()).catch(()=>void 0)}catch{}}var Ht=class{constructor(e){this.host=e,this._subscribedEntity=``,this._generation=0,this._retryDelay=zt,this._onDisconnected=()=>{this.host.onOffline(!0)},this._onReady=()=>{this.host.onOffline(!1),this.host.hasLoadError()&&this.retry()}}resetBackoff(){this._retryDelay=zt}ensure(){let e=this.host.hass(),t=this.host.entity();if(!this.host.isConnected()||!e?.connection||!t||this._subscribedEntity===t&&this._connection===e.connection)return;this.reset(),this._attach(e.connection),this._subscribedEntity=t;let n=++this._generation;e.connection.subscribeMessage(e=>{n===this._generation&&(this._retryDelay=zt,this.host.onPayload(e))},{type:Rt,entity_id:t},{resubscribe:!0}).then(e=>{n===this._generation?this._unsubscribe=e:Vt(e)},e=>{if(n!==this._generation)return;let t=e?.code;this.host.onLoadError(t===`not_found`||t===`invalid_format`?`not_found`:t===`unauthorized`?`unauthorized`:`load_failed`),this._scheduleRetry()})}_scheduleRetry(){this._retryTimer&&clearTimeout(this._retryTimer),this._retryTimer=setTimeout(()=>{this._retryTimer=void 0,this.retry()},this._retryDelay),this._retryDelay=Math.min(this._retryDelay*2,Bt)}retry(){this.reset(),this.ensure()}_attach(e){e.addEventListener?.(`disconnected`,this._onDisconnected),e.addEventListener?.(`ready`,this._onReady),this._connection=e,e.connected===!1&&this.host.onOffline(!0)}reset(){this._generation++,this._unsubscribe&&Vt(this._unsubscribe),this._unsubscribe=void 0,this._retryTimer&&clearTimeout(this._retryTimer),this._retryTimer=void 0,this._connection?.removeEventListener?.(`disconnected`,this._onDisconnected),this._connection?.removeEventListener?.(`ready`,this._onReady),this._connection=void 0,this._subscribedEntity=``}},Ut=2e3,Wt=432e5;function Gt(e){if(!e)return;let t=Date.parse(e);return Number.isFinite(t)?t:void 0}function H(e,t,n=0){if(e.state===`finished`)return 0;if(e.state===`paused`)return Math.max(Math.floor(e.remaining??0),0);let r=Gt(e.ends_at);return r===void 0?0:Math.max(Math.ceil((r-(t+n))/1e3),0)}function Kt(e,t,n=0){return e.state===`running`&&H(e,t,n)<=0?`finished`:e.state}function qt(e){let t=Math.max(Math.floor(e),0),n=Math.floor(t/3600),r=Math.floor(t%3600/60),i=t%60,a=e=>String(e).padStart(2,`0`);return n>0?`${n}:${a(r)}:${a(i)}`:`${a(r)}:${a(i)}`}function Jt(e,t,n=0){let r=e.minutes*60;if(!(r>0))return 1;let i=H(e,t,n);return Math.min(Math.max(1-i/r,0),1)}function Yt(e,t){if(!e||e.state!==`running`)return;let n=Gt(e.started_at),r=Gt(e.ends_at);if(n===void 0||r===void 0||r-n!==e.minutes*6e4)return;let i=n-t;return Math.abs(i)<Ut||Math.abs(i)>Wt?0:i}function Xt(e,t){return!e||!t?!e&&!t:e.subtask===t.subtask&&e.state===t.state&&e.minutes===t.minutes&&(e.state!==`paused`||e.remaining===t.remaining)&&(e.state===`paused`||e.ends_at===t.ends_at)}function Zt(e){return`${e.subtask}|${e.started_at}`}function Qt(e,t){let n=t.prewarn_minutes;if(!(!n||n<1))return e.minutes>n?n*60:void 0}function U(e,t,n,r){let i=n+(r.skewMs??0),a=e=>new Date(e).toISOString();switch(e){case`start`:{let e=r.info;return e?{subtask:e.uid,title:e.title,subject:e.subject,due:e.due,label:e.label,state:`running`,ends_at:a(i+e.minutes*6e4),minutes:e.minutes,started_at:a(i)}:t}case`pause`:{if(!t||t.state!==`running`)return t;let e={...t};return delete e.ends_at,{...e,state:`paused`,remaining:Math.max(r.secondsLeft??1,1)}}case`resume`:{if(!t||t.state!==`paused`)return t;let e={...t};return delete e.remaining,{...e,state:`running`,ends_at:a(i+(t.remaining??0)*1e3)}}case`extend`:{let e=r.extra;return!t||!e?t:{...t,state:`running`,minutes:e,ends_at:a(i+e*6e4)}}case`stop`:case`done`:return null}}function $t(e,t){if(e===null||e===``||e===void 0)return null;let n=typeof e==`number`?e:Number(e);if(!(!Number.isInteger(n)||n<1||n>t))return n}function en(e){let t=$t(e.prewarn_minutes,15);if(t===void 0)return{ok:!1,field:`prewarn_minutes`};let n=$t(e.extra_minutes,30);return n===void 0?{ok:!1,field:`extra_minutes`}:{ok:!0,settings:{prewarn_minutes:t,extra_minutes:n}}}function tn(e,t){return e.prewarn_minutes===t.prewarn_minutes&&e.extra_minutes===t.extra_minutes}function nn(e){return{prewarn_minutes:e?.prewarn_minutes??null,extra_minutes:e?.extra_minutes??null}}var rn=/* @__PURE__ */ new Set([`not_allowed_for_role`,`unauthorized`]);function an(e,t){let n=e.override??null;return n?.mode===`replace`?n.label.name:e.info_type!==null&&n?.mode!==`disable`?At(t,e.info_type,e.label??``):e.manual_labels[0]?.name??``}function on(e,t){return V(e,t).split(` · `).map(e=>e.trim()).filter(e=>e!==``).join(` · `)}var sn=`magister.notifications`,cn=`magister.notify.claim.`,ln=`magister.notifications.constructorBroken`,un=`magister-notifications`,dn=12e4,fn=864e5;function W(e){try{return window.localStorage.getItem(e)}catch{return null}}function pn(e,t){try{return window.localStorage.setItem(e,t),!0}catch{return!1}}function mn(){let e=W(sn);if(e!==null)try{let t=JSON.parse(e);return{enabled:t?.enabled===!0,sound:t?.sound!==!1}}catch{}return{enabled:!1,sound:!0}}var hn=/* @__PURE__ */ new Set;function gn(e){return hn.add(e),()=>{hn.delete(e)}}function _n(){for(let e of[...hn])e()}var vn,yn=!1,bn=!1;function G(e){vn=e,yn=!pn(sn,JSON.stringify(e)),_n()}function K(){return yn&&vn?vn:mn()}typeof window<`u`&&typeof window.addEventListener==`function`&&window.addEventListener(`storage`,e=>{(e.key===sn||e.key===ln||e.key===null)&&_n()});var xn=!1;function Sn(){if(!xn){xn=!0;try{navigator.permissions?.query({name:`notifications`}).then(e=>{e.onchange=()=>{_n()}}).catch(()=>void 0)}catch{}}}function Cn(){return typeof window>`u`?`unsupported`:typeof navigator<`u`&&navigator.userAgent.includes(`Home Assistant/`)?`app`:window.Notification===void 0||bn||W(ln)===`1`?`unsupported`:window.isSecureContext?`ok`:`insecure`}function wn(){return typeof window<`u`&&window.Notification!==void 0?window.Notification.permission:`unsupported`}function Tn(){let e=Cn(),t=wn(),n=K();return{availability:e,permission:t,active:e===`ok`&&t===`granted`&&n.enabled,sound:n.sound}}async function En(e,t=`Notifications are on`){if(!e){G({...K(),enabled:!1});return}if(Cn()!==`ok`)return;An();let n=window.Notification.permission;if(n==="default")try{n=await window.Notification.requestPermission()}catch{n=window.Notification.permission}n===`granted`&&!Dn(t)?(bn=!0,pn(ln,`1`),G({...K(),enabled:!1})):G({...K(),enabled:n===`granted`})}function Dn(e){try{return new window.Notification(e,{tag:`magister-test`,silent:!0}).close(),!0}catch{return!1}}function On(e){G({...K(),sound:e}),e&&An()}var q;function kn(){if(q)return q;try{let e=window,t=e.AudioContext??e.webkitAudioContext;if(!t)return;q=new t}catch{q=void 0}return q}function An(){try{let e=kn();e?.state===`suspended`?e.resume().then(()=>{e.state===`running`&&Mn()}).catch(()=>void 0):e?.state===`running`&&Mn()}catch{}}function J(){let e=Tn();e.active&&e.sound&&An()}var Y=!1;function jn(){Y||typeof window>`u`||typeof window.addEventListener!=`function`||(Y=!0,window.addEventListener(`pointerdown`,J,!0),window.addEventListener(`keydown`,J,!0))}function Mn(){Y&&(Y=!1,window.removeEventListener(`pointerdown`,J,!0),window.removeEventListener(`keydown`,J,!0))}jn();function Nn(){try{let e=kn();if(!e)return;e.state===`suspended`&&e.resume().catch(()=>void 0);let t=e.currentTime;for(let[n,r]of[[0,880],[.22,1175]]){let i=e.createOscillator(),a=e.createGain();i.type=`sine`,i.frequency.value=r,a.gain.setValueAtTime(1e-4,t+n),a.gain.exponentialRampToValueAtTime(.25,t+n+.02),a.gain.exponentialRampToValueAtTime(1e-4,t+n+.18),i.connect(a),a.connect(e.destination),i.start(t+n),i.stop(t+n+.2)}}catch{}}var Pn=/* @__PURE__ */ new Set,X,Fn=Math.random().toString(36).slice(2);function In(){if(X)return X;try{if(typeof BroadcastChannel>`u`)return;X=new BroadcastChannel(un),X.onmessage=e=>{let t=e.data;typeof t?.claim==`string`&&Pn.add(t.claim)}}catch{X=void 0}return X}function Ln(){In(),Sn()}function Rn(e){let t=[e.child,e.startedAt,e.moment];return e.moment===`end`&&t.push(e.endsAt??``),t.join(`|`)}function zn(){try{let e=Date.now(),t=[];for(let n=0;n<window.localStorage.length;n++){let r=window.localStorage.key(n);if(!r?.startsWith(cn))continue;let i=Number(window.localStorage.getItem(r)?.split(`|`)[1]);(!Number.isFinite(i)||e-i>fn)&&t.push(r)}for(let e of t)window.localStorage.removeItem(e)}catch{}}function Bn(e){if(Pn.has(e))return!1;Pn.add(e);let t=cn+e,n=`${Fn}|${Date.now()}`;if(W(t)!==null||pn(t,n)&&W(t)!==n)return!1;zn();try{In()?.postMessage({claim:e})}catch{}return!0}function Vn(e){try{if(In(),!Tn().active)return;let t=Rn(e),n=typeof navigator>`u`?void 0:navigator.locks;if(typeof n?.request==`function`){n.request(cn+t,{ifAvailable:!0},async n=>{n&&Bn(t)&&(Hn(e),await new Promise(e=>setTimeout(e,dn)))}).catch(()=>void 0);return}if(!Bn(t))return;Hn(e)}catch{}}function Hn(e){let{sound:t}=K();t&&Nn();try{let t=new window.Notification(e.text,{tag:`magister-timer-${e.child}`,lang:e.language,renotify:!0});t.onclick=()=>{try{window.focus()}finally{t.close()}}}catch{}}var Un=`magister/homework/timer`,Wn=`magister/homework/timer_settings`,Gn=1e4,Kn=50,qn=class{constructor(e,t){this.host=e,this.deps=t,this.settingsOpen=!1,this.settingsForm={prewarn:``,extra:``,error:``},this.locked=!1,this.announcement=``,this.skewMs=0,this.notifyOpen=!1,this._token=0,this._moments=[]}now(){return Date.now()}timer(){return this.override?this.override.timer:this.deps.payload()?.timer??null}settings(){return this.settingsOverride??nn(this.deps.payload()?.timer_settings)}view(){let e=this.timer();if(!e)return;let t=this.now();return{timer:e,state:Kt(e,t,this.skewMs),remaining:H(e,t,this.skewMs),fraction:Jt(e,t,this.skewMs)}}viewFor(e){let t=this.view();return t?.timer.subtask===e?t:void 0}extraMinutes(e){return e?.state===`finished`?this.settings().extra_minutes:null}reset(){this.override=void 0,this.settingsOverride=void 0,this.confirmUid=void 0,this.panel=void 0,this.settingsOpen=!1,this.locked=!1,this.lockCode=void 0,this._pending=void 0,this._settingsPending=void 0,this._seen=void 0,this.skewMs=0,this._setAnnouncement(``),this._arm(),this.sync()}connected(){Ln(),this._unsubscribe??=gn(()=>{this.host.requestUpdate()}),!this._visibility&&typeof document<`u`&&(this._visibility=()=>{this._arm(),this.observe(),this.host.requestUpdate()},document.addEventListener(`visibilitychange`,this._visibility)),this._arm(),this.sync()}disconnected(){this._unsubscribe?.(),this._unsubscribe=void 0,this._visibility&&document.removeEventListener(`visibilitychange`,this._visibility),this._visibility=void 0,this._disarm(),this._stopTicker(),this._announceTimer&&clearTimeout(this._announceTimer),this._announceTimer=void 0}onPayload(){this._pending===void 0&&(this.override=void 0),this._settingsPending===void 0&&(this.settingsOverride=void 0),this._validate(),this.observe(),this._arm(),this.sync()}_disarm(){for(let e of this._moments)clearTimeout(e);this._moments=[]}_arm(){if(this._disarm(),!this.host.isConnected)return;let e=this.view();if(e?.state!==`running`||e.timer.state!==`running`)return;let t=[],n=e.timer.prewarned===!0?void 0:Qt(e.timer,this.settings());n!==void 0&&e.remaining>n&&t.push((e.remaining-n)*1e3),t.push(e.remaining*1e3);for(let e of t)this._moments.push(setTimeout(()=>{this.observe(),this.host.requestUpdate()},e+Kn))}_validate(){let e=this.timer();this.panel&&(!e||e.subtask!==this.panel.uid)&&(this.panel=void 0),this.confirmUid&&!this._info(this.confirmUid)&&(this.confirmUid=void 0)}willUpdate(){this.deps.canWrite()||(this.confirmUid=void 0),this._validate()}sync(){let e=this.view();e?.state===`running`&&e.timer.state===`running`&&this.host.isConnected?this._ticker??=setInterval(()=>{this.tick()},1e3):this._stopTicker()}_stopTicker(){this._ticker&&clearInterval(this._ticker),this._ticker=void 0}tick(){this.observe(),this.host.requestUpdate(),this.sync()}get ticking(){return this._ticker!==void 0}observe(){let e=this.view();if(!e){this._seen=void 0;return}let{timer:t,state:n,remaining:r}=e,i=Zt(t);this._seen?.key!==i&&(this._seen={key:i,prewarnDone:t.prewarned===!0,endDone:!1,sawActive:!1,lastRemaining:void 0});let a=this._seen,o=this.deps.texts();if(n===`running`||n===`paused`){if(a.sawActive=!0,a.endDone=!1,!a.prewarnDone){let e=Qt(t,this.settings());if(e===void 0)a.prewarnDone=!0;else if(r<=e&&(a.prewarnDone=!0,n===`running`&&a.lastRemaining!==void 0&&a.lastRemaining>e)){let n=Math.max(Math.round(e/60),1);this._setAnnouncement(V(n===1?o.timer.announce_prewarn_one:o.timer.announce_prewarn,{n,title:t.title})),this._notify(`prewarn`,V(n===1?o.timer.notify_prewarn_one:o.timer.notify_prewarn,{n,what:Jn(t)}))}}}else a.prewarnDone=!0,a.endDone||(a.endDone=!0,a.sawActive&&(this._setAnnouncement(V(o.timer.announce_end,{title:t.title})),this._notify(`end`,V(o.timer.notify_end,{what:Jn(t)}))));a.lastRemaining=r}_notify(e,t){let n=this.timer();n&&Vn({child:this.deps.entity()??``,startedAt:n.started_at,endsAt:n.ends_at,moment:e,text:t,language:this.deps.texts().timer.language})}_setAnnouncement(e){this._announceTimer&&clearTimeout(this._announceTimer),this._announceTimer=void 0,this.announcement=e,this.host.requestUpdate(),e!==``&&(this._announceTimer=setTimeout(()=>{this.announcement=``,this._announceTimer=void 0,this.host.requestUpdate()},Gn))}_find(e){for(let t of this.deps.payload()?.items??[]){let n=t.subtasks?.find(t=>t.uid===e);if(n)return{subtask:n,item:t}}}_info(e){let t=this._find(e);if(t&&typeof t.subtask.minutes==`number`)return{uid:e,title:t.subtask.title,minutes:t.subtask.minutes,subject:t.item.subject,due:t.item.date,label:this.deps.itemLabel?.(t.item)??t.item.label??``}}labelOf(e){let t=this.view()?.timer.label??``,n=this._find(e);return n?this.deps.itemLabel?.(n.item)??n.item.label??t:t}progressOf(e){return this._find(e)?.subtask.progress??0}get disabled(){return!this.deps.canWrite()||this.locked}start(e,t,n=!1){if(this.disabled)return;let r=this._info(e);if(!r)return;let i=this.view(),a=i!==void 0&&i.state!==`finished`;if(a&&!n){this.confirmUid=e,this.host.requestUpdate(),this._focus([`.timer-confirm [data-timer-cancel]`]);return}this.confirmUid=void 0;let o=U(`start`,i?.timer??null,this.now(),{info:r,skewMs:this.skewMs});this._run(`start`,{subtask:e,...a?{replace:!0}:{}},o,{focus:[Z(`pause`,e,t),Z(`pause`,e,`bar`)],onResult:(e,t)=>{let n=Yt(e,t);n!==void 0&&(this.skewMs=n)}})}cancelConfirm(e){this.confirmUid=void 0,this.host.requestUpdate(),this._focus([`[data-timer-start="${Q(e)}"]`])}pause(e){let t=this.view();if(this.disabled||t?.state!==`running`)return;let n=U(`pause`,t.timer,this.now(),{secondsLeft:t.remaining});this._run(`pause`,{},n,{focus:[Z(`resume`,t.timer.subtask,e)]})}resume(e){let t=this.view();if(this.disabled||t?.state!==`paused`)return;let n=U(`resume`,t.timer,this.now(),{skewMs:this.skewMs});this._run(`resume`,{},n,{focus:[Z(`pause`,t.timer.subtask,e)]})}extend(e){let t=this.view(),n=this.settings().extra_minutes;if(this.disabled||t?.state!==`finished`||!n)return;let r=U(`extend`,t.timer,this.now(),{extra:n,skewMs:this.skewMs});this._run(`extend`,{},r,{focus:[Z(`pause`,t.timer.subtask,e),Z(`pause`,t.timer.subtask,`bar`)]})}done(){let e=this.view();if(this.disabled||e?.state!==`finished`)return;let t=e.timer.subtask;this._run(`done`,{},null,{progress:{uid:t,value:100},focus:this._afterFocus(t)})}openPanel(){let e=this.view();if(this.disabled||!e)return;let t=e.timer.subtask;this.settingsOpen=!1,this.panel={uid:t,selected:Ie(this.progressOf(t))},this.host.requestUpdate(),this._focus([`.timer-panel [role="radio"][tabindex="0"]`])}selectStep(e){this.panel&&j.includes(e)&&(this.panel={...this.panel,selected:e},this.host.requestUpdate(),this._focus([`.timer-panel [role="radio"][tabindex="0"]`]))}closePanel(){this.panel&&(this.panel=void 0,this.host.requestUpdate(),this._focus([`[data-timer-act="stop"]`,`[data-timer-act="not_yet"]`]))}stop(e){let t=this.panel,n=this.view();!this.disabled&&t&&n&&n.timer.subtask===t.uid&&(this.panel=void 0,this._run(`stop`,e?{progress:t.selected}:{},null,{...e?{progress:{uid:t.uid,value:t.selected}}:{},focus:this._afterFocus(t.uid)}))}_afterFocus(e){return[`[data-timer-start="${Q(e)}"]`,...this.deps.fallbackFocus?.()??[]]}async _run(e,t,n,r){let i=this.deps.hass(),a=this.deps.entity();if(!i||!a)return;let o=++this._token;this._pending=o,this.override={timer:n};let s=r.progress?this.deps.beginProgress?.(r.progress.uid,r.progress.value):void 0;this.host.requestUpdate(),this.observe(),this._arm(),this.sync(),r.focus&&this._focus(r.focus);try{let n=await i.callWS({type:Un,entity_id:a,action:e,...t});if(s?.(!0),this._pending!==o)return;this._pending=void 0,r.onResult?.(n.timer,this.now()),this.override=Xt(this.deps.payload()?.timer,n.timer)?void 0:{timer:n.timer}}catch(e){if(s?.(!1),this._pending!==o)return;this._pending=void 0,this.override=void 0;let t=e?.code;this._fail(t)}this.host.requestUpdate(),this.observe(),this._arm(),this.sync()}_fail(e){let t=this.deps.texts().timer.errors;e!==void 0&&rn.has(e)&&this.deps.lockOnDenied===!0&&(this.locked=!0,this.lockCode=e),this.deps.showError((e?t[e]:void 0)??t.default??``)}openSettings(){let e=this.settings();this.panel=void 0,this.settingsForm={prewarn:e.prewarn_minutes===null?``:String(e.prewarn_minutes),extra:e.extra_minutes===null?``:String(e.extra_minutes),error:``},this.settingsOpen=!0,this.host.requestUpdate(),this._focus([`.timer-settings select`])}closeSettings(){this.settingsOpen=!1,this.host.requestUpdate(),this._focus([`[data-timer-settings-button]`])}patchSettings(e){this.settingsForm={...this.settingsForm,...e,error:``},this.host.requestUpdate()}async saveSettings(){let e=this.deps.hass(),t=this.deps.entity();if(this.disabled||!e||!t||!this.settingsOpen)return;let n=this.settingsForm,r=en({prewarn_minutes:n.prewarn,extra_minutes:n.extra}),i=this.deps.texts().timer.errors;if(!r.ok){this.settingsForm={...n,error:i.invalid_format??``},this.host.requestUpdate();return}let a=r.settings;if(tn(a,this.settings())){this.closeSettings();return}let o=++this._token;this._settingsPending=o,this.settingsOverride=a,this.settingsOpen=!1,this.host.requestUpdate(),this.observe(),this._arm(),this._focus([`[data-timer-settings-button]`]);try{let n=await e.callWS({type:Wn,entity_id:t,prewarn_minutes:a.prewarn_minutes,extra_minutes:a.extra_minutes});if(this._settingsPending!==o)return;this._settingsPending=void 0;let r=nn(n.timer_settings);this.settingsOverride=tn(nn(this.deps.payload()?.timer_settings),r)?void 0:r}catch(e){if(this._settingsPending!==o)return;this._settingsPending=void 0,this.settingsOverride=void 0;let t=e?.code;t!==void 0&&rn.has(t)&&this.deps.lockOnDenied===!0&&(this.locked=!0,this.lockCode=t),this.settingsForm={...n,error:(t?i[t]:void 0)??i.default??``},this.settingsOpen=!0,this._focus([`.timer-settings .timer-error`,`.timer-settings select`])}this.host.requestUpdate(),this.observe(),this._arm()}afterRender(){if(!this.settingsOpen)return;let e=this.settingsForm;for(let[t,n]of[[`#timer-prewarn`,e.prewarn],[`#timer-extra`,e.extra]]){let e=this.host.shadowRoot?.querySelector(t);e&&e.value!==n&&(e.value=n)}}_focus(e){this.host.updateComplete.then(()=>{for(let t of e){let e=this.host.shadowRoot?.querySelector(t);if(e){e.focus();return}}})}};function Jn(e){return e.subject?`${e.title} (${e.subject})`:e.title}function Z(e,t,n){return`[data-timer-act="${e}"][data-timer-uid="${Q(t)}"][data-timer-where="${n}"]`}function Q(e){return typeof CSS<`u`&&typeof CSS.escape==`function`?CSS.escape(e):e.replace(/["\\]/g,`\\$&`)}var $={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},Yn=e=>(...t)=>({_$litDirective$:e,values:t}),Xn=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}},{I:Zn}=je,Qn=e=>e.strings===void 0,$n={},er=(e,t=$n)=>e._$AH=t,tr=Yn(class extends Xn{constructor(e){if(super(e),e.type!==$.PROPERTY&&e.type!==$.ATTRIBUTE&&e.type!==$.BOOLEAN_ATTRIBUTE)throw Error("The `live` directive is not allowed on child or event bindings");if(!Qn(e))throw Error("`live` bindings can only contain a single expression")}render(e){return e}update(e,[t]){if(t===w||t===T)return t;let n=e.element,r=e.name;if(e.type===$.PROPERTY){if(t===n[r])return w}else if(e.type===$.BOOLEAN_ATTRIBUTE){if(!!t===n.hasAttribute(r))return w}else if(e.type===$.ATTRIBUTE&&n.getAttribute(r)===t+``)return w;return er(e),t}}),nr={play:`M8,5.14V19.14L19,12.14Z`,pause:`M14,19H18V5H14M6,19H10V5H6V19Z`,stop:`M18,18H6V6H18V18Z`,done:`M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z`},rr=e=>C`<svg class="glyph" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d=${nr[e]??``}></path></svg>`,ir=(e,t)=>e.timer[t.state];function ar(e){return C`<div class="sr-only timer-live" role="status" aria-live="polite" aria-atomic="true">${e.controller.announcement}</div>`}function or(e,t,n=``){let{texts:r}=e;return C`<span class="countdown ${t.state} ${n}" role="timer" aria-live="off"
    ><span class="sr-only">${V(r.timer.countdown_aria,{title:t.timer.title,state:ir(r,t)})}: </span
    >${qt(t.remaining)}</span
  >`}function sr(e,t,n,r){let{texts:i,controller:a}=e,o=P(r,e.language);return C`<button
    type="button"
    class="icon-btn timer-start"
    data-timer-start=${t}
    ?disabled=${!e.enabled||a.disabled}
    title=${i.timer.start}
    aria-label=${V(i.timer.start_aria,{title:n,time:o})}
    @click=${()=>{a.start(t,`row`)}}
  >${rr(`play`)}</button>`}function cr(e,t,n){let{texts:r,controller:i}=e,a=!e.enabled||i.disabled,o=t.timer.subtask,s=t.timer.title,c=n===`card`,l=(e,t,r,i,s,l=``,u=!1)=>C`<button
    type="button"
    class="timer-btn ${l} ${c?`big`:``}"
    data-timer-act=${e}
    data-timer-uid=${o}
    data-timer-where=${n}
    ?disabled=${a}
    title=${r}
    aria-label=${i}
    @click=${s}
  >${t?rr(t):T}${c||u||!t?C`<span class="label">${r}</span>`:T}</button>`;if(t.state===`finished`){let e=i.extraMinutes(t);return C`<span class="timer-actions" role="group" aria-label=${V(r.timer.finished_group,{title:s})}>
      ${l(`done`,`done`,r.timer.done,V(r.timer.done_aria,{title:s}),()=>{i.done()},`primary`,!0)}
      ${e?l(`extend`,``,V(r.timer.extra,{n:e}),V(r.timer.extra_aria,{n:e,title:s}),()=>{i.extend(n)},``,!0):T}
      ${l(`not_yet`,``,r.timer.not_yet,V(r.timer.not_yet_aria,{title:s}),()=>{i.openPanel()},``,!0)}
    </span>`}return C`<span class="timer-actions">
    ${t.state===`running`?l(`pause`,`pause`,r.timer.pause,V(r.timer.pause_aria,{title:s}),()=>{i.pause(n)}):l(`resume`,`play`,r.timer.resume,V(r.timer.resume_aria,{title:s}),()=>{i.resume(n)})}
    ${l(`stop`,`stop`,r.timer.stop,V(r.timer.stop_aria,{title:s}),()=>{i.openPanel()})}
  </span>`}function lr(e){let{controller:t,texts:n}=e,r=t.panel,i=t.view();if(!r||!i)return T;let a=!e.enabled||t.disabled,o=i.timer.title,s=e=>{let n=j.indexOf(r.selected),i;switch(e.key){case`ArrowRight`:case`ArrowDown`:i=Math.min(n+1,j.length-1);break;case`ArrowLeft`:case`ArrowUp`:i=Math.max(n-1,0);break;case`Home`:i=0;break;case`End`:i=j.length-1;break;default:return}e.preventDefault();let a=j[i];a!==void 0&&t.selectStep(a)};return C`<section
    class="timer-panel"
    role="group"
    aria-labelledby="timer-panel-title"
    @keydown=${e=>{e.key===`Escape`&&(e.stopPropagation(),t.closePanel())}}
  >
    <h4 id="timer-panel-title" class="timer-panel-title">${n.timer.panel_title}</h4>
    <p class="meta timer-panel-for">${o}</p>
    <div class="steps" role="radiogroup" aria-label=${V(n.timer.panel_aria,{title:o})}>
      ${j.map(e=>C`<button
          type="button"
          role="radio"
          class="step ${e===r.selected?`selected`:``}"
          aria-checked=${e===r.selected?`true`:`false`}
          aria-label=${V(n.percent,{n:e})}
          tabindex=${e===r.selected?0:-1}
          ?disabled=${a}
          @click=${()=>{t.selectStep(e)}}
          @keydown=${s}
        >${e}</button>`)}
    </div>
    <div class="timer-panel-actions">
      <button type="button" class="cancel" @click=${()=>{t.closePanel()}}>${n.timer.panel_cancel}</button>
      <button type="button" class="discard" ?disabled=${a} @click=${()=>{t.stop(!1)}}>${n.timer.panel_discard}</button>
      <button type="button" class="primary" ?disabled=${a} @click=${()=>{t.stop(!0)}}>${n.timer.panel_save}</button>
    </div>
  </section>`}function ur(e,t,n){let{controller:r,texts:i}=e,a=r.view();if(r.confirmUid!==t||!a)return T;let o=V(i.timer.confirm_replace,{title:a.timer.title});return C`<div
    class="timer-confirm"
    role="group"
    aria-label=${o}
    @keydown=${e=>{e.key===`Escape`&&(e.stopPropagation(),r.cancelConfirm(t))}}
  >
    <span>${o}</span>
    <button type="button" class="cancel" data-timer-cancel aria-label=${V(i.timer.confirm_no_aria,{title:n})} @click=${()=>{r.cancelConfirm(t)}}>${i.timer.confirm_no}</button>
    <button type="button" class="primary" data-timer-replace ?disabled=${!e.enabled||r.disabled} @click=${()=>{r.start(t,`row`,!0)}}>${i.timer.confirm_yes}</button>
  </div>`}function dr(e){let{controller:t,texts:n}=e;return C`<button
    type="button"
    class="timer-settings-btn"
    data-timer-settings-button
    aria-expanded=${t.settingsOpen?`true`:`false`}
    title=${n.timer.settings}
    aria-label=${n.timer.settings}
    @click=${()=>{t.settingsOpen?t.closeSettings():t.openSettings()}}
  ><span aria-hidden="true">⚙</span></button>`}var fr=e=>Array.from({length:e},(e,t)=>t+1);function pr(e){let{texts:t}=e,n=Tn(),r=t.timer,i;return i=n.availability===`ok`?C`<label class="notify-row">
        <input
          type="checkbox"
          id="timer-notify"
          .checked=${tr(n.active)}
          @change=${e=>{En(e.target.checked,r.notify_confirm)}}
        />
        <span>${r.notify_enable}</span>
      </label>
      ${n.permission===`denied`?C`<p class="timer-error notify-denied" role="status">${r.notify_denied}</p>
            <p class="meta">${r.notify_denied_hint}</p>`:T}
      ${n.active?C`<label class="notify-row">
            <input
              type="checkbox"
              id="timer-notify-sound"
              .checked=${tr(n.sound)}
              @change=${e=>{On(e.target.checked)}}
            />
            <span>${r.notify_sound}</span>
          </label>`:T}
      <p class="meta">${r.notify_hint}</p>`:C`<p class="meta notify-unavailable">${{app:r.notify_app,insecure:r.notify_insecure,unsupported:r.notify_unsupported}[n.availability]}</p>`,C`<div class="timer-notify" role="group" aria-label=${r.notify_title}>${i}</div>`}function mr(e,t,n){let{texts:r}=e;return C`<div class="notify-bar">
    <button
      type="button"
      class="notify-btn"
      data-notify-button
      aria-expanded=${t?`true`:`false`}
      @click=${n}
    ><span aria-hidden="true">⚙</span> ${r.timer.notify_title}</button>
    ${t?C`<div
          class="timer-settings notify-panel"
          tabindex="-1"
          @keydown=${e=>{e.key===`Escape`&&(e.stopPropagation(),n())}}
        >${pr(e)}</div>`:T}
  </div>`}function hr(e){let{controller:t,texts:n}=e;if(!t.settingsOpen)return T;let r=t.settingsForm,i=!e.enabled||t.disabled,a=(e,t,a,o,s)=>C`<label>
    <span>${t}</span>
    <select
      id=${e}
      ?disabled=${i}
      aria-invalid=${r.error?`true`:`false`}
      aria-describedby=${r.error?`timer-settings-error`:T}
      @change=${e=>{s(e.target.value)}}
    >
      <option value="" ?selected=${o===``}>${n.timer.off}</option>
      ${fr(a).map(e=>C`<option value=${String(e)} ?selected=${o===String(e)}>${V(n.timer.minutes_option,{n:e})}</option>`)}
    </select>
  </label>`;return C`<form
    class="timer-settings"
    role="group"
    aria-label=${n.timer.settings_title}
    novalidate
    @submit=${e=>{e.preventDefault(),t.saveSettings()}}
    @keydown=${e=>{e.key===`Escape`&&(e.stopPropagation(),t.closeSettings())}}
  >
    <h4 class="timer-panel-title">${n.timer.settings_title}</h4>
    ${a(`timer-prewarn`,n.timer.prewarn,15,r.prewarn,e=>{t.patchSettings({prewarn:e})})}
    ${a(`timer-extra`,n.timer.extra_minutes,30,r.extra,e=>{t.patchSettings({extra:e})})}
    <p class="meta">${n.timer.settings_hint}</p>
    ${r.error?C`<p class="timer-error" id="timer-settings-error" role="alert" tabindex="-1">${r.error}</p>`:T}
    <div class="timer-panel-actions">
      <button type="button" class="cancel" @click=${()=>{t.closeSettings()}}>${n.timer.cancel}</button>
      <button type="submit" class="primary" ?disabled=${i}>${n.timer.save}</button>
    </div>
  </form>
  <div
    class="timer-settings notify-panel"
    @keydown=${e=>{e.key===`Escape`&&(e.stopPropagation(),t.closeSettings())}}
  >${pr(e)}</div>`}var gr=o`
  :host {
    --timer-color: var(--primary-color, #03a9f4);
    --timer-warn: var(--warning-color, #ffa600);
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }
  .glyph {
    width: 18px;
    height: 18px;
    fill: currentColor;
  }
  .countdown {
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    color: var(--primary-text-color);
  }
  .countdown.paused {
    color: var(--secondary-text-color);
  }
  .timer-actions {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
  }
  .timer-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-width: 36px;
    min-height: 36px;
    padding: 0 12px;
    border: 1px solid var(--divider-color);
    border-radius: 18px;
    background: transparent;
    color: var(--primary-text-color);
    font: inherit;
    font-size: 0.85em;
    cursor: pointer;
  }
  .timer-btn.primary {
    border-color: var(--timer-color);
    background: var(--timer-color);
    color: var(--text-primary-color, #fff);
  }
  .timer-btn.big {
    min-height: 56px;
    min-width: 56px;
    padding: 0 22px;
    border-radius: 28px;
    font-size: 1.1em;
  }
  .timer-btn:disabled,
  .timer-start:disabled,
  .timer-panel button:disabled,
  .timer-settings button:disabled,
  .timer-confirm button:disabled {
    cursor: default;
    opacity: 0.6;
  }
  .timer-btn:focus-visible,
  .timer-start:focus-visible,
  .timer-settings-btn:focus-visible,
  .timer-panel button:focus-visible,
  .timer-settings button:focus-visible,
  .timer-settings select:focus-visible,
  .timer-confirm button:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .timer-start {
    color: var(--timer-color);
  }
  .timer-notify {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding-top: 6px;
    border-top: 1px solid var(--divider-color);
  }
  .notify-row {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 36px;
    cursor: pointer;
  }
  .notify-row input {
    width: 20px;
    height: 20px;
    margin: 0;
    accent-color: var(--primary-color);
  }
  .notify-row input:focus-visible,
  .notify-btn:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .notify-bar {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    margin-top: 12px;
  }
  .notify-bar .notify-panel {
    align-self: stretch;
  }
  .notify-btn {
    min-height: 36px;
    padding: 0 12px;
    border: 1px solid var(--divider-color);
    border-radius: 18px;
    background: transparent;
    color: var(--secondary-text-color);
    font: inherit;
    font-size: 0.9em;
    cursor: pointer;
  }
  .timer-settings-btn {
    min-width: 36px;
    min-height: 36px;
    padding: 0;
    border: 1px solid var(--divider-color);
    border-radius: 18px;
    background: transparent;
    color: var(--secondary-text-color);
    font: inherit;
    font-size: 1.1em;
    cursor: pointer;
  }
  .timer-panel,
  .timer-settings,
  .timer-confirm {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: 8px 0;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid color-mix(in srgb, var(--timer-color) 50%, transparent);
    background: color-mix(in srgb, var(--timer-color) 8%, transparent);
    font-size: 0.9em;
  }
  .timer-confirm {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    margin: 6px 0 0;
    padding: 6px 8px;
  }
  .timer-panel-title {
    margin: 0;
    font-size: 1.05em;
    font-weight: 600;
    color: var(--primary-text-color);
  }
  .timer-panel-for {
    margin: 0;
    overflow-wrap: anywhere;
  }
  .steps {
    display: flex;
    border: 1px solid var(--divider-color);
    border-radius: 8px;
    overflow: hidden;
    max-width: 320px;
  }
  .step {
    flex: 1;
    min-height: 44px;
    padding: 0;
    border: none;
    border-left: 1px solid var(--divider-color);
    background: transparent;
    color: var(--secondary-text-color);
    font: inherit;
    cursor: pointer;
  }
  .step:first-child {
    border-left: none;
  }
  .step.selected {
    background: var(--timer-color);
    color: var(--text-primary-color, #fff);
    font-weight: 700;
  }
  .timer-panel-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: flex-end;
  }
  .timer-panel-actions button,
  .timer-confirm button {
    min-height: 40px;
    padding: 0 14px;
    border-radius: 20px;
    border: 1px solid var(--divider-color);
    background: transparent;
    color: var(--primary-text-color);
    font: inherit;
    font-size: 0.9em;
    cursor: pointer;
  }
  .timer-panel .primary,
  .timer-settings .primary,
  .timer-confirm .primary {
    border-color: var(--timer-color);
    background: var(--timer-color);
    color: var(--text-primary-color, #fff);
  }
  .timer-settings label {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 0.85em;
    color: var(--secondary-text-color);
  }
  .timer-settings select {
    min-height: 40px;
    max-width: 220px;
    padding: 0 8px;
    border: 1px solid var(--divider-color);
    border-radius: 6px;
    background: transparent;
    color: var(--primary-text-color);
    font: inherit;
    font-size: 1.05em;
  }
  .timer-error {
    margin: 0;
    color: var(--error-color);
  }
  .timer-track {
    height: 4px;
    margin-top: 6px;
    border-radius: 2px;
    overflow: hidden;
    background: var(--divider-color);
  }
  .timer-fill {
    height: 100%;
    background: var(--timer-color);
  }
  @media (pointer: coarse) {
    .timer-btn,
    .icon-btn.timer-start,
    .icon-btn.timer-settings-btn,
    .timer-start,
    .timer-settings-btn {
      min-height: 44px;
      min-width: 44px;
    }
  }
`,_r=`magister/homework/set_progress`,vr=`magister/homework/remove_label`,yr=`magister/homework/set_override`,br=`magister/homework/add_subtask`,xr=`magister/homework/update_subtask`,Sr=`magister/homework/delete_subtask`,Cr=`magister/homework/respond_proposal`,wr=100,Tr=6e3,Er=`M16.5,6V17.5A4,4 0 0,1 12.5,21.5A4,4 0 0,1 8.5,17.5V5A2.5,2.5 0 0,1 11,2.5A2.5,2.5 0 0,1 13.5,5V15.5A1,1 0 0,1 12.5,16.5A1,1 0 0,1 11.5,15.5V6H10V15.5A2.5,2.5 0 0,0 12.5,18A2.5,2.5 0 0,0 15,15.5V5A4,4 0 0,0 11,1A4,4 0 0,0 7,5V17.5A5.5,5.5 0 0,0 12.5,23A5.5,5.5 0 0,0 18,17.5V6H16.5Z`,Dr=`M19,15L13,21L11.58,19.58L15.17,16H4V4H6V14H15.17L11.58,10.42L13,9L19,15Z`,Or=class extends A{static{this.properties={_payload:{state:!0},_loadError:{state:!0},_offline:{state:!0},_overlay:{state:!0},_expanded:{state:!0},_toast:{state:!0},_showCompleted:{state:!0},_showPast:{state:!0},_hiddenLabels:{state:!0},_confirm:{state:!0},_dialogOpen:{state:!0},_overrideOverlay:{state:!0},_menu:{state:!0},_subEdits:{state:!0},_form:{state:!0},_subConfirm:{state:!0},_proposalOverlay:{state:!0},_proposalConfirm:{state:!0}}}constructor(){super(),this._storageKey=``,this._removing=/* @__PURE__ */ new Set,this._tokens=/* @__PURE__ */ new Map,this._overrideTokens=/* @__PURE__ */ new Map,this._subTokens=/* @__PURE__ */ new Map,this._proposalTokens=/* @__PURE__ */ new Map,this._focusForm=!1,this._nextToken=0,this._hassKey=``,this._shownDay=``,this._touched=/* @__PURE__ */ new Set,this._onOutsideClick=e=>{let t=this._menu;if(t===void 0)return;let n=e.composedPath(),r=this.shadowRoot?.querySelector(`.menu`);r&&n.includes(r)||n.includes(this._menuButton(t))||this._closeMenu(!1)},this._closeDialog=()=>{this._dialogOpen=!1,this.updateComplete.then(()=>{this.shadowRoot?.querySelector(`.add`)?.focus()})},this._subscription=new Ht({isConnected:()=>this.isConnected,hass:()=>this._hass,entity:()=>this._config?.entity,onPayload:e=>{this._onPayload(e)},onLoadError:e=>{this._loadError=e},onOffline:e=>{this._offline=e},hasLoadError:()=>this._loadError!==void 0}),this._timer=new qn(this,{hass:()=>this._hass,entity:()=>this._config?.entity,payload:()=>this._payload,canWrite:()=>this._payload?.available===!0&&!this._offline,texts:()=>this._texts(),showError:e=>{this._showToast(e)},itemLabel:e=>this._itemLabel(e,this._texts()),fallbackFocus:()=>[`.toolbar .switch`],beginProgress:(e,t)=>this._beginProgress(e,t)}),this._offline=!1,this._overlay=/* @__PURE__ */ new Map,this._expanded=/* @__PURE__ */ new Set,this._toast=``,this._showCompleted=!1,this._showPast=!1,this._hiddenLabels=/* @__PURE__ */ new Set,this._confirm=void 0,this._dialogOpen=!1,this._overrideOverlay=/* @__PURE__ */ new Map,this._menu=void 0,this._subEdits=/* @__PURE__ */ new Map,this._form=void 0,this._subConfirm=void 0,this._proposalOverlay=/* @__PURE__ */ new Map,this._proposalConfirm=void 0}static getConfigElement(){return document.createElement(`magister-homework-card-editor`)}static getStubConfig(e){return{entity:Object.entries(e?.entities??{}).find(([e,t])=>e.startsWith(`todo.`)&&t?.platform===`magister`)?.[0]??``}}setConfig(e){let t=ut(e);t.entity!==this._config?.entity&&(this._subscription.reset(),this._payload=void 0,this._loadError=void 0,this._offline=!1,this._overlay=/* @__PURE__ */ new Map,this._expanded=/* @__PURE__ */ new Set,this._tokens.clear(),this._touched.clear(),this._hiddenLabels=/* @__PURE__ */ new Set,this._removing.clear(),this._confirm=void 0,this._dialogOpen=!1,this._overrideOverlay=/* @__PURE__ */ new Map,this._overrideTokens.clear(),this._subEdits=/* @__PURE__ */ new Map,this._subTokens.clear(),this._proposalOverlay=/* @__PURE__ */ new Map,this._proposalTokens.clear(),this._proposalConfirm=void 0,this._form=void 0,this._subConfirm=void 0,this._pendingFocus=void 0,this._timer.reset(),this._closeMenu(!1),this._subscription.resetBackoff()),this._config=t,this._storageKey=_t(t);let n=vt(this._storageKey);this._showCompleted=n?.show_completed??t.show_completed,this._showPast=n?.show_past??t.show_past,this.requestUpdate(),this._subscription.ensure()}set hass(e){this._hass=e;let t=`${e?.locale?.language??``}|${e?.language??``}|${e?.config?.time_zone??``}`;t===this._hassKey&&this._payload||(this._hassKey=t,this.requestUpdate()),this._subscription.ensure()}get hass(){return this._hass}getCardSize(){let e=this._visibleItems().length;return e===0?3:2+e*2}getGridOptions(){return{columns:12,min_columns:6,min_rows:3}}connectedCallback(){super.connectedCallback(),this._subscription.ensure(),this._timer.connected(),this._dayTimer=setInterval(()=>{this._currentDay()!==this._shownDay&&this.requestUpdate()},6e4)}disconnectedCallback(){super.disconnectedCallback(),this._subscription.reset(),this._timer.disconnected(),this._toastTimer&&clearTimeout(this._toastTimer),this._dayTimer&&clearInterval(this._dayTimer),this._dayTimer=void 0,this._closeMenu(!1)}_onPayload(e){this._payload=e,this._loadError=void 0,this._offline=!1;let t=/* @__PURE__ */ new Map;for(let[e,n]of this._overlay)this._tokens.has(e)&&t.set(e,n);this._overlay=t;let n=/* @__PURE__ */ new Map;for(let[e,t]of this._overrideOverlay)this._overrideTokens.has(e)&&n.set(e,t);this._overrideOverlay=n;let r=/* @__PURE__ */ new Map;for(let[e,t]of this._subEdits)this._subTokens.has(e)&&r.set(e,t);this._subEdits=r;let i=/* @__PURE__ */ new Map;for(let[e,t]of this._proposalOverlay)this._proposalTokens.has(e)&&i.set(e,t);this._proposalOverlay=i,this._hiddenLabels=new Set([...this._hiddenLabels].filter(e=>this._removing.has(e))),this._timer.onPayload()}_beginProgress(e,t){let n=this._findTarget(e);if(!n)return()=>void 0;let r=++this._nextToken;this._tokens.set(e,r),t>=100&&(this._touched.add(e),this._touched.add(I(e)));let i={...n,...this._overlay.get(e)};return this._overlay=new Map(this._overlay).set(e,Ue(i,t)),n=>{if(this._tokens.get(e)!==r)return;this._tokens.delete(e);let i=new Map(this._overlay);n&&this._findTarget(e)?.progress!==t||i.delete(e),this._overlay=i}}async _setProgress(e,t){let n=this._hass,r=this._config?.entity,i=this._findTarget(e);if(!n||!r||!i||!this._payload?.available||this._offline)return;let a=++this._nextToken;this._tokens.set(e,a),t>=100&&(this._touched.add(e),this._touched.add(I(e)));let o=Ue({...i,...this._overlay.get(e)},t);this._overlay=new Map(this._overlay).set(e,o);try{let i=await n.callWS({type:_r,entity_id:r,item:e,progress:t});if(this._tokens.get(e)!==a)return;this._tokens.delete(e);let s=this._findTarget(e),c=new Map(this._overlay);s?.progress===i.progress?c.delete(e):c.set(e,{...o,progress:i.progress,completed:i.completed}),this._overlay=c}catch(t){if(this._tokens.get(e)!==a)return;this._tokens.delete(e);let n=new Map(this._overlay);n.delete(e),this._overlay=n;let r=t?.code,i=this._texts();this._showToast(r===`unauthorized`?i.save_unauthorized:r===`item_disabled`?i.label_errors.item_disabled??i.save_failed:r===`item_has_subtasks`||r===`item_not_found`&&e.includes(`:sub:`)?i.sub.errors[r]??i.save_failed:i.save_failed)}}_findTarget(e){for(let t of this._payload?.items??[]){if(t.uid===e)return t;let n=t.subtasks?.find(t=>t.uid===e);if(n)return n}}_showToast(e){this._toast=e,this._toastTimer&&clearTimeout(this._toastTimer),this._toastTimer=setTimeout(()=>{this._toast=``},Tr)}_toggleExpanded(e){let t=new Set(this._expanded);t.delete(e)||t.add(e),this._expanded=t}_menuButton(e){return this.shadowRoot?.querySelector(`[data-menu-button="${CSS.escape(e)}"]`)??null}_menuItems(){return[...this.shadowRoot?.querySelectorAll(`.menu [role="menuitem"]`)??[]]}_openMenu(e,t){this._menu=e,document.addEventListener(`click`,this._onOutsideClick,!0),this.updateComplete.then(()=>{let e=this._menuItems();(t===`first`?e[0]:e[e.length-1])?.focus()})}_closeMenu(e){let t=this._menu;document.removeEventListener(`click`,this._onOutsideClick,!0),t!==void 0&&(this._menu=void 0,e&&this.updateComplete.then(()=>{this._menuButton(t)?.focus()}))}_onChipKey(e,t){e.key===`ArrowDown`?(e.preventDefault(),this._openMenu(t,`first`)):e.key===`ArrowUp`?(e.preventDefault(),this._openMenu(t,`last`)):e.key===`Escape`&&this._menu===t&&(e.preventDefault(),this._closeMenu(!0))}_onMenuKey(e,t){let n=this._menuItems(),r=n.indexOf(e.target),i;switch(e.key){case`ArrowDown`:i=(r+1)%n.length;break;case`ArrowUp`:i=(r-1+n.length)%n.length;break;case`Home`:i=0;break;case`End`:i=n.length-1;break;case`Escape`:e.preventDefault(),e.stopPropagation(),this._closeMenu(!0);return;case`Tab`:this._menuButton(t)?.focus(),this._closeMenu(!1);return;default:return}e.preventDefault(),n[i]?.focus()}_choose(e,t){this._closeMenu(!0),this._setOverride(e,t)}async _setOverride(e,t){let n=this._hass,r=this._config?.entity,i=e.uid;if(!n||!r||!this._payload?.available||this._offline)return;let a=++this._nextToken;this._overrideTokens.set(i,a),t.mode===`disable`&&this._touched.add(i);let o=this._items().find(e=>e.uid===i)??e;this._overrideOverlay=new Map(this._overrideOverlay).set(i,xt(o,t));try{let e=await n.callWS({type:yr,entity_id:r,appointment:i,mode:t.mode,...t.mode===`replace`?{label:t.label.id}:{}});if(this._overrideTokens.get(i)!==a)return;this._overrideTokens.delete(i);let o=new Map(this._overrideOverlay),s=this._payload.items.find(e=>e.uid===i),c=e.item?St(e.item):void 0;!c||s&&wt(s,c)?o.delete(i):o.set(i,c),this._overrideOverlay=o}catch(e){if(this._overrideTokens.get(i)!==a)return;this._overrideTokens.delete(i);let t=new Map(this._overrideOverlay);t.delete(i),this._overrideOverlay=t;let n=e?.code,r=this._texts();this._showToast((n?r.label_errors[n]:void 0)??r.save_failed)}}_proposals(){return tt(this._payload?.proposals??[],this._proposalOverlay)}_proposalSummary(e,t){let n=this._language()===`nl`?`nl`:`en`;if(e.kind===`weekdays`){let r=(e.weekdays??[]).map((e,r)=>`${t.proposal.weekdays_short[r]??``} ${e===0?t.proposal.none:Ze(e,n)}`).join(`, `);return V(t.proposal.weekdays,{reason:e.reason,values:r})}return V(t.proposal.period,{reason:e.reason,range:rt(e.start??``,e.end??``,n===`nl`?`nl`:`en-GB`),max:P(e.minutes??0,n)})}_proposalSummaryHtml(e,t){if(e.kind===`weekdays`)return this._proposalSummary(e,t);let n=this._language()===`nl`?`nl`:`en`,r=rt(e.start??``,e.end??``,n===`nl`?`nl`:`en-GB`),i=V(t.proposal.period,{reason:e.reason,range:`\0`,max:P(e.minutes??0,n)}).split(`\0`);return i.length===2?C`${i[0]}<span class="nowrap">${r}</span>${i[1]}`:this._proposalSummary(e,t)}_expiryText(e,t,n){return e.kind===`period`?V(t.proposal.answer_by,{date:L(N(e.expires,-1),n)}):V(t.proposal.expires,{date:L(e.expires,n)})}_askAccept(e){this._toast=``,this._proposalConfirm=e,this.updateComplete.then(()=>{this.shadowRoot?.querySelector(`.proposal .confirm .cancel`)?.focus()})}_cancelAccept(e){this._proposalConfirm=void 0,this.updateComplete.then(()=>{this.shadowRoot?.querySelector(`[data-accept="${CSS.escape(e)}"]`)?.focus()})}async _respond(e,t){let n=this._hass,r=this._config?.entity;if(this._proposalConfirm=void 0,!n||!r||!this._payload?.available||this._offline)return;let i=e.id,a=++this._nextToken;this._proposalTokens.set(i,a);let o=this._proposals().filter(e=>F(e)&&e.id!==i);this._proposalOverlay=new Map(this._proposalOverlay).set(i,{status:t===`accept`?`accepted`:`rejected`,closed:this._currentDay()}),this._focusAfter([...o.map(e=>`[data-proposal="${CSS.escape(e.id)}"] button`),`.toolbar .switch`]);let s=this._texts();try{let e=await n.callWS({type:Cr,entity_id:r,proposal:i,answer:t});if(this._proposalTokens.get(i)!==a)return;this._proposalTokens.delete(i);let o=new Map(this._proposalOverlay),c=this._payload.proposals?.find(e=>e.id===i);c&&c.status!==`proposed`?o.delete(i):o.set(i,{status:e.proposal.status,closed:e.proposal.closed,answered_by:e.proposal.answered_by}),this._proposalOverlay=o,this._showToast(t===`accept`?s.proposal.accepted_toast:s.proposal.rejected_toast)}catch(e){if(this._proposalTokens.get(i)!==a)return;this._proposalTokens.delete(i);let t=new Map(this._proposalOverlay);t.delete(i),this._proposalOverlay=t;let n=e?.code;this._showToast((n?s.proposal.errors[n]:void 0)??s.proposal.errors.default??s.save_failed),this._focusAfter([`[data-proposal="${CSS.escape(i)}"] button`])}}_renderProposals(e,t){let n=this._proposals().filter(F);if(n.length===0)return T;let r=this._language()===`nl`?`nl`:`en-GB`;return C`<div class="proposals">
      ${n.map(n=>{let i=this._proposalSummary(n,e),a=this._proposalConfirm===n.id;return C`<section
          class="proposal"
          role="group"
          data-proposal=${n.id}
          aria-label=${V(e.proposal.group_aria,{summary:i})}
        >
          <p class="proposal-text">
            <span class="proposal-title">${e.proposal.title}:</span> ${this._proposalSummaryHtml(n,e)}
            <span class="proposal-expires">${this._expiryText(n,e,r)}</span>
          </p>
          ${a?C`<div
                class="confirm"
                role="group"
                aria-label=${e.proposal.confirm}
                @keydown=${e=>{e.key===`Escape`&&(e.stopPropagation(),this._cancelAccept(n.id))}}
              >
                <span>${e.proposal.confirm}</span>
                <button type="button" class="cancel" @click=${()=>{this._cancelAccept(n.id)}}>${e.proposal.confirm_no}</button>
                <button type="button" class="primary" ?disabled=${!t} @click=${()=>{this._respond(n,`accept`)}}>${e.proposal.confirm_yes}</button>
              </div>`:C`<div class="proposal-actions">
                <button
                  type="button"
                  class="primary"
                  data-accept=${n.id}
                  ?disabled=${!t}
                  aria-label=${V(e.proposal.accept_aria,{summary:i})}
                  @click=${()=>{this._askAccept(n.id)}}
                >${e.proposal.accept}</button>
                <button
                  type="button"
                  class="reject"
                  data-reject=${n.id}
                  ?disabled=${!t}
                  aria-label=${V(e.proposal.reject_aria,{summary:i})}
                  @click=${()=>{this._respond(n,`reject`)}}
                >${e.proposal.reject}</button>
              </div>`}
        </section>`})}
    </div>`}_renderClosedProposals(e){if(!this._showPast)return T;let t=this._proposals().filter(e=>!F(e));if(t.length===0)return T;let n=this._language()===`nl`?`nl`:`en-GB`;return C`<section class="closed-proposals" aria-labelledby="closed-proposals-title">
      <h3 class="section" id="closed-proposals-title">${e.proposal.earlier}</h3>
      <ul>
        ${t.map(t=>{let r=e.proposal[t.status],i=t.answered_by===`on_behalf`?` ${e.proposal.on_behalf}`:``,a=t.closed?V(e.proposal.closed_on,{status:`${r}${i}`,date:L(t.closed,n)}):`${r}${i}`;return C`<li class="closed-proposal" data-proposal=${t.id}>
            <span class="proposal-status ${t.status}">${a}</span>
            <span>${this._proposalSummaryHtml(t,e)}</span>
          </li>`})}
      </ul>
    </section>`}_askRemove(e,t){this._confirm={uid:e,label:t},this.updateComplete.then(()=>{this.shadowRoot?.querySelector(`.confirm .cancel`)?.focus()})}_cancelRemove(){let e=this._confirm;this._confirm=void 0,e&&this.updateComplete.then(()=>{this.shadowRoot?.querySelector(`[data-key="${CSS.escape(z(e.uid,e.label.id))}"]`)?.focus()})}async _removeLabel(e,t){let n=this._hass,r=this._config?.entity;if(this._confirm=void 0,!n||!r)return;let i=z(e,t.id);this._removing.add(i),this._hiddenLabels=new Set(this._hiddenLabels).add(i),this.updateComplete.then(()=>{let t=this.shadowRoot?.querySelector(`li[data-uid="${CSS.escape(e)}"]`);(t?.querySelector(`.chip-remove:not(:disabled)`)??t?.querySelector(`input[type="checkbox"]`)??this.shadowRoot?.querySelector(`.add`))?.focus()});try{await n.callWS({type:vr,entity_id:r,appointment:e,label:t.id}),this._removing.delete(i)}catch(e){this._removing.delete(i);let t=e?.code;if(t===`label_not_on_appointment`)return;let n=new Set(this._hiddenLabels);n.delete(i),this._hiddenLabels=n;let r=this._texts();this._showToast((t?r.label_errors[t]:void 0)??r.save_failed)}}_language(){return Ot(this._config?.language,this._hass?.locale?.language??this._hass?.language)}_texts(){return Dt[this._language()]}_items(){return this._payload?dt(Tt(qe(at(this._payload.items,this._subEdits,this._currentDay()),this._overlay),this._overrideOverlay),this._hiddenLabels):[]}_setSwitch(e,t){e===`show_completed`?this._showCompleted=t:this._showPast=t,yt(this._storageKey,{show_completed:this._showCompleted,show_past:this._showPast})}_currentDay(){return ze(/* @__PURE__ */ new Date,this._hass?.config?.time_zone)}_today(){return this._shownDay=this._currentDay(),this._shownDay}_visibleGroups(){let e=this._config;return!e||!this._payload?[]:ct(this._items(),{showCompleted:this._showCompleted,showPast:this._showPast,daysAhead:e.days_ahead,today:this._today(),keep:this._touched})}_visibleItems(){return this._visibleGroups().flatMap(e=>e.entries)}_dayTitle(e,t){return e.kind===`overdue`?t.sub.overdue_group:e.kind===`today`?t.today:e.kind===`tomorrow`?t.tomorrow:Be(e.date,this._language()===`nl`?`nl`:`en-GB`)}willUpdate(){this._timer.willUpdate(),this._confirm&&(this._offline||this._payload?.available!==!0)&&(this._confirm=void 0);let e=this._offline||this._payload?.available!==!0;this._form&&(e||!this._formTarget(this._form))&&(this._form=void 0),this._subConfirm&&(e||!this._findSubtask(this._subConfirm))&&(this._subConfirm=void 0);let t=this._proposalConfirm;t!==void 0&&(e||!this._proposals().some(e=>e.id===t&&F(e)))&&(this._proposalConfirm=void 0),this._menu!==void 0&&(this._offline||this._payload?.available!==!0||!this._payload.items.some(e=>e.uid===this._menu))&&this._closeMenu(!1)}render(){let e=this._config,t=this._texts();return C`<ha-card .header=${e?.title??``}>
      ${this._timerUi()?ar(this._timerContext(t)):T}
      <div class="content ${e?.title?`titled`:``}">${this._renderBody(t)}</div>
      ${this._toast?C`<div class="toast" role="alert">
            <span>${this._toast}</span>
            <button type="button" @click=${()=>{this._toast=``}}>${t.dismiss}</button>
          </div>`:T}
      ${this._renderDialog(t)}
    </ha-card>`}_renderBody(e){if(!this._config?.entity)return C`<p class="state">${e.choose_entity}</p>`;if(this._loadError)return C`<p class="state error">${e[this._loadError]}</p>`;if(!this._payload)return C`<p class="state">${e.loading}</p>`;let t=this._payload.available,n=t&&!this._offline,r=this._visibleGroups(),i=this._renderBars(e,this._offline),a=C`${this._renderTimerBar(e)}${this._renderProposals(e,n)}${this._renderToolbar(e,n)}${this._timerUi()?hr(this._timerContext(e)):T}${i}${t?T:C`<p class="banner" role="status">${e.unavailable}</p>`}${this._offline?C`<p class="banner" role="status">${e.offline}</p>`:T}`,o=this._renderClosedProposals(e);if(r.length===0)return t?C`${a}<p class="state empty">${e.no_homework}</p>${o}`:C`${a}${o}`;let s=r.findIndex(e=>e.kind===`past`),c=Xe(this._items());return C`${a}<div class="days ${t?``:`stale`}">
        ${r.map((t,r)=>C`
            ${r===s?C`<h3 class="section">${e.earlier}</h3>`:T}
            <section class="day" aria-labelledby="day-${t.date}">
              <div class="day-head">
                <h4 id="day-${t.date}" class=${t.kind}>${this._dayTitle(t,e)}</h4>
                ${this._renderPlanned(t,c,e)}${this._renderProposedMax(t,e)}
              </div>
              <ul>
                ${t.entries.map(t=>this._renderEntry(t,e,n))}
              </ul>
            </section>
          `)}
      </div>${o}`}_renderPlanned(e,t,n){if(e.kind===`overdue`)return T;let r=t.get(e.date)??0;if(r<=0)return T;let i=this._language()===`nl`?`nl`:`en`,{max:a,adjusted:o}=et(this._payload,e.date),s=V(n.sub.planned,{time:P(r,i)});if(typeof a!=`number`)return C`<span class="planned">${s}</span>`;let c=r>a;if(!c&&!o)return C`<span class="planned">${s}</span>`;let l=P(a,i),u=V(c&&a===0?o?n.sub.over_zero_adjusted_max:n.sub.over_zero_max:o?c?n.sub.over_adjusted_max:n.sub.adjusted_max:n.sub.over_max,{max:l}),d=V(o?n.sub.max_short_adjusted:n.sub.max_short,{max:l});return C`<span class=${[`planned`,c?`over`:``,o?`adjusted`:``].filter(e=>e!==``).join(` `)} title=${u}
      >${c?C`<span aria-hidden="true">⚠ </span>`:T}${s}<span aria-hidden="true">
        ${d}</span
      ><span class="sr-only">, ${u}</span></span
    >`}_renderProposedMax(e,t){if(e.kind===`overdue`)return T;let n=nt(this._proposals(),e.date);if(n===void 0)return T;let r=P(n,this._language()===`nl`?`nl`:`en`);return C`<span class="proposed-max" title=${V(t.proposal.day_note_aria,{max:r})}
      ><span aria-hidden="true">${V(t.proposal.day_note,{max:r})}</span
      ><span class="sr-only">${V(t.proposal.day_note_aria,{max:r})}</span></span
    >`}_timerUi(){let e=this._payload;return e!==void 0&&(e.timer!==void 0||e.timer_settings!==void 0)}_timerContext(e){return{controller:this._timer,texts:e,language:this._language()===`nl`?`nl`:`en`,enabled:this._payload?.available===!0&&!this._offline}}_renderTimerBar(e){if(!this._timerUi())return T;let t=this._timerContext(e),n=this._timer.view();if(!n)return T;let r=this._language()===`nl`?`nl`:`en-GB`,i=on(e.timer.meta,{subject:n.timer.subject,label:this._timer.labelOf(n.timer.subtask),date:L(n.timer.due,r)});return C`<section class="timer-bar ${n.state}" aria-label=${e.timer.region}>
      <div class="timer-bar-row">
        <div class="timer-bar-text">
          <span class="timer-bar-title">${n.timer.title}</span>
          <span class="meta">${i}</span>
        </div>
        ${n.state===`finished`?C`<span class="timer-state finished">${e.timer.finished}</span>`:C`${or(t,n,`bar-countdown`)}${n.state===`paused`?C`<span class="timer-state">${e.timer.paused}</span>`:T}`}
        ${cr(t,n,`bar`)}
      </div>
      <div class="timer-track" aria-hidden="true">
        <div class="timer-fill" style="width: ${Math.round(n.fraction*100)}%"></div>
      </div>
      ${lr(t)}
    </section>`}_renderRowTimer(e,t){if(!this._timerUi())return T;let n=this._timerContext(t),r=this._timer.viewFor(e.uid);return C`${r?C`<div class="timer-row ${r.state}">
          ${r.state===`finished`?C`<span class="timer-state finished">${t.timer.finished}</span>`:C`${or(n,r)}${r.state===`paused`?C`<span class="timer-state">${t.timer.paused}</span>`:T}`}
          ${cr(n,r,`row`)}
        </div>`:T}${ur(n,e.uid,e.title)}`}_renderToolbar(e,t){let n=this._payload?.labels??[],r=t&&n.length>0,i=(e,t,n,r)=>C`<button
      type="button"
      class="switch ${t?`on`:``}"
      aria-pressed=${t?`true`:`false`}
      title=${r}
      aria-label=${r}
      @click=${()=>{this._setSwitch(e,!t)}}
    ><span aria-hidden="true" class="tick">${t?`✓`:``}</span>${n}</button>`;return C`<div class="toolbar" role="toolbar" aria-label=${e.switches_label}>
      ${i(`show_completed`,this._showCompleted,e.show_completed_switch,e.show_completed_tip)}
      ${i(`show_past`,this._showPast,e.show_past_switch,e.show_past_tip)}
      ${this._timerUi()?dr(this._timerContext(e)):T}
      ${r?C`<button
            type="button"
            class="add"
            title=${e.add_label}
            aria-label=${e.add_label}
            aria-haspopup="dialog"
            @click=${()=>{this._dialogOpen=!0}}
          >+</button>`:T}
    </div>`}_renderDialog(e){let t=this._payload,n=this._config;if(!this._dialogOpen||!t||!n)return T;let r=this._currentDay(),i=ft(t.items,r,n.days_ahead);return C`<magister-label-dialog
      .hass=${this._hass}
      .entity=${n.entity}
      .labels=${t.labels??[]}
      .texts=${e}
      .language=${this._language()}
      .today=${r}
      .min=${i.min}
      .max=${i.max}
      @dialog-closed=${this._closeDialog}
    ></magister-label-dialog>`}_renderBars(e,t){let n=this._config,r=this._payload?.progress,i=R.filter(({option:e})=>n?.[e]);return i.length===0?T:C`<div class="bars ${t?`stale`:``}">
      ${i.map(({period:t})=>{let n=e.progress_label[t],i=r?.[t]??null;if(!i)return C`<div class="bar unavailable">
            <div class="bar-head"><span>${n}</span></div>
            <div
              class="track"
              role="progressbar"
              aria-label=${n}
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuetext=${e.progress_unavailable}
            ></div>
            <div class="bar-note">${e.progress_unavailable}</div>
          </div>`;let a=lt(i),o=V(e.percent,{n:a}),s=i.items===0?e.progress_empty:V(e.progress_done,{completed:i.completed,items:i.items});return C`<div class="bar">
          <div class="bar-head"><span>${n}</span><span class="bar-value">${o}</span></div>
          <div
            class="track"
            role="progressbar"
            aria-label=${n}
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow=${a}
            aria-valuetext="${o}, ${s}"
          >
            <div class="fill" style="width: ${a}%"></div>
          </div>
          <div class="bar-note">${s}</div>
        </div>`})}
    </div>`}_renderItem(e,t,n){let r=this._expanded.has(e.uid),i=e.manual_labels.filter(e=>e.note!==``),a=this._confirm?.uid===e.uid?this._confirm.label:void 0,o=e.uid,s=[`item`,e.is_test?`test`:``,e.completed?`done`:``,e.disabled===!0?`disabled`:``,e.cancelled?`cancelled`:``].filter(Boolean).join(` `),c=Ge(e);return C`<li class=${s} data-uid=${o}>
      ${c?C`<input
            type="checkbox"
            .checked=${e.completed}
            disabled
            aria-label=${V(t.sub.derived_check,{subject:e.subject})}
          />`:C`<input
            type="checkbox"
            .checked=${e.completed}
            ?disabled=${!n||e.disabled===!0}
            aria-label=${V(e.completed?t.mark_open:t.mark_done,{subject:e.subject})}
            @change=${()=>void this._setProgress(e.uid,Le(e))}
          />`}
      <div class="main">
        <div class="head">
          ${this._renderMagisterChip(e,t,n)}
          ${e.manual_labels.map(r=>this._renderManualChip(e.uid,r,t,n))}
          <span class="subject">${e.subject}</span>
          ${this._renderMarker(e,t)}
          ${e.lesson_hour===null?T:C`<span class="meta">${V(t.lesson_hour,{n:e.lesson_hour})}</span>`}
          ${e.cancelled?C`<span class="badge">${t.cancelled}</span>`:T}
          ${e.has_attachments?C`<span class="meta attachments" title=${t.attachments}
                ><svg viewBox="0 0 24 24" aria-hidden="true"><path d=${Er}></path></svg
                ><span class="sr-only">${t.attachments}</span></span
              >`:T}
        </div>
        ${this._menu===e.uid?this._renderMenu(e,t):T}
        ${e.text?C`<button
              type="button"
              class="text ${r?`expanded`:``}"
              aria-expanded=${r?`true`:`false`}
              title=${r?t.collapse:t.expand}
              @click=${()=>{this._toggleExpanded(e.uid)}}
            >${e.text}</button>`:T}
        ${i.map(e=>C`<p class="note"><span class="note-label">${e.name}</span> ${e.note}</p>`)}
        ${a?C`<div
              class="confirm"
              role="group"
              aria-label=${V(t.confirm_remove,{name:a.name})}
              @keydown=${e=>{e.key===`Escape`&&(e.stopPropagation(),this._cancelRemove())}}
            >
              <span>${V(t.confirm_remove,{name:a.name})}</span>
              <button type="button" class="cancel" @click=${()=>{this._cancelRemove()}}>${t.confirm_no}</button>
              <button type="button" class="danger" ?disabled=${!n} @click=${()=>{this._removeLabel(e.uid,a)}}>${t.confirm_yes}</button>
            </div>`:T}
        ${c?this._renderDerived(e,t):this._renderProgress(e,V(t.progress_of,{subject:e.subject}),t,n&&e.disabled!==!0)}
        ${this._renderAddSubtask(e,t,n)}
      </div>
    </li>`}_renderMarker(e,t){let n=e.disabled===!0?0:e.subtasks?.length??0;if(n===0)return T;let r=n===1,i=V(r?t.sub.marker_aria_one:t.sub.marker_aria,{n});return C`<span class="sub-marker" role="img" title=${i} aria-label=${i}
      ><svg viewBox="0 0 24 24" aria-hidden="true"><path d=${Dr}></path></svg
      ><span aria-hidden="true">${V(r?t.sub.marker_one:t.sub.marker,{n})}</span></span
    >`}_renderEntry(e,t,n){return e.type===`item`?this._renderItem(e.item,t,n):this._renderSubtask(e.subtask,e.parent,t,n)}_findSubtask(e){for(let t of this._payload?.items??[]){let n=t.subtasks?.find(t=>t.uid===e);if(n)return n}}_formTarget(e){let t=this._payload?.items.find(t=>t.uid===e.itemUid);if(t&&t.disabled!==!0&&(e.mode!==`edit`||t.subtasks?.some(t=>t.uid===e.subUid)))return t}_dateBounds(e){let t=this._currentDay();return e.date<=t?{min:e.date,max:e.date,fixed:!0}:{min:t,max:e.date,fixed:!1}}_clampDate(e,t){return e<t.min?t.min:e>t.max?t.max:e}_itemLabel(e,t){return an(e,t)}_renderDerived(e,t){let n=e.subtasks??[],r=n.filter(e=>e.completed).length,i=V(n.length===1?t.sub.count_one:t.sub.count,{done:r,total:n.length}),a=V(t.percent,{n:e.progress});return C`<div class="progress derived">
      <div
        class="track"
        role="progressbar"
        aria-label=${V(t.progress_of,{subject:e.subject})}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=${e.progress}
        aria-valuetext=${V(t.sub.derived_value,{count:i,n:e.progress})}
        title=${t.sub.derived_hint}
      >
        <div class="fill" style="width: ${e.progress}%"></div>
      </div>
      <span class="percent">${a}</span>
      <span class="meta sub-count">${i}</span>
    </div>`}_renderAddSubtask(e,t,n){if(e.disabled===!0)return T;let r=this._form,i=r?.mode===`add`&&r.itemUid===e.uid;return C`${n?C`<button
          type="button"
          class="link add-sub"
          data-add-sub=${e.uid}
          aria-expanded=${i?`true`:`false`}
          aria-label=${V(t.sub.add_aria,{subject:e.subject})}
          @click=${()=>{this._openForm({mode:`add`,itemUid:e.uid},e)}}
        >${t.sub.add}</button>`:T}${i?this._renderSubForm(r,e,t):T}`}_renderSubtask(e,t,n,r){let i=this._language()===`nl`?`nl`:`en-GB`,a=this._form,o=a?.mode===`edit`&&a.subUid===e.uid?a:void 0,s=this._subConfirm===e.uid,c=V(n.sub.for_item,{label:this._itemLabel(t,n),subject:t.subject,date:L(t.date,i)}).replace(/\s+/g,` `);return C`<li class=${[`item`,`subtask`,e.completed?`done`:``,e.overdue?`overdue`:``].filter(Boolean).join(` `)} data-uid=${e.uid}>
      <input
        type="checkbox"
        .checked=${e.completed}
        ?disabled=${!r}
        aria-label=${V(e.completed?n.sub.mark_open:n.sub.mark_done,{title:e.title})}
        @change=${()=>void this._setProgress(e.uid,Le(e))}
      />
      <div class="main">
        ${o?this._renderSubForm(o,t,n):C`<div class="head">
              <span class="arrow" aria-hidden="true">↳</span>
              <span class="subject sub-title">${e.title}</span>
              ${e.created_by===`ai`?C`<span
                    class="ai-badge"
                    role="img"
                    title=${n.sub.ai_label}
                    aria-label=${n.sub.ai_label}
                  ><span aria-hidden="true">${n.sub.ai}</span></span>`:e.created_by===`parent`?C`<span
                      class="ai-badge parent-badge"
                      role="img"
                      title=${n.sub.parent_label}
                      aria-label=${n.sub.parent_label}
                    ><span aria-hidden="true">${n.sub.parent}</span></span>`:T}
              ${typeof e.minutes==`number`?C`<span class="sub-minutes"
                    ><span class="sr-only">${n.sub.minutes}: </span>${P(e.minutes,this._language()===`nl`?`nl`:`en`)}</span
                  >`:T}
              ${r?C`<span class="sub-actions">${this._timerUi()&&typeof e.minutes==`number`&&!e.completed&&!this._timer.viewFor(e.uid)?sr(this._timerContext(n),e.uid,e.title,e.minutes):T}<button
                      type="button"
                      class="icon-btn"
                      data-edit=${e.uid}
                      title=${n.sub.edit}
                      aria-label=${V(n.sub.edit_aria,{title:e.title})}
                      @click=${()=>{this._openForm({mode:`edit`,itemUid:t.uid,subUid:e.uid},t)}}
                    >✎</button>
                    <button
                      type="button"
                      class="icon-btn"
                      data-delete=${e.uid}
                      title=${n.sub.delete}
                      aria-label=${V(n.sub.delete_aria,{title:e.title})}
                      @click=${()=>{this._askDeleteSubtask(e.uid)}}
                    >✕</button></span>`:T}
            </div>
            <div class="meta ref">${e.overdue?C`<span class="badge">${n.sub.overdue}</span> `:T}${c}</div>`}
        ${s?C`<div
              class="confirm subconfirm"
              role="group"
              aria-label=${V(n.sub.confirm_delete,{title:e.title})}
              @keydown=${t=>{t.key===`Escape`&&(t.stopPropagation(),this._cancelDeleteSubtask(e.uid))}}
            >
              <span>${V(n.sub.confirm_delete,{title:e.title})}</span>
              <button type="button" class="cancel" @click=${()=>{this._cancelDeleteSubtask(e.uid)}}>${n.confirm_no}</button>
              <button type="button" class="danger" ?disabled=${!r} @click=${()=>{this._deleteSubtask(e.uid)}}>${n.sub.confirm_yes}</button>
            </div>`:T}
        ${this._renderRowTimer(e,n)}
        ${this._renderProgress(e,V(n.sub.progress_of,{title:e.title}),n,r)}
      </div>
    </li>`}_renderSubForm(e,t,n){let r=this._dateBounds(t),i=e.mode===`add`?V(n.sub.form_add,{subject:t.subject}):V(n.sub.form_edit,{title:t.subtasks?.find(t=>t.uid===e.subUid)?.title??``}),a=`sub-error-${e.mode}`;return C`<form
      class="subform"
      aria-label=${i}
      novalidate
      @submit=${e=>{e.preventDefault(),this._submitForm()}}
      @keydown=${e=>{e.key===`Escape`&&(e.stopPropagation(),this._cancelForm())}}
    >
      <label>
        <span>${n.sub.title}</span>
        <input
          class="sub-title-input"
          type="text"
          required
          maxlength=${wr}
          .value=${e.title}
          ?disabled=${e.busy}
          aria-invalid=${e.error?`true`:`false`}
          aria-describedby=${e.error?a:T}
          @input=${e=>{this._patchForm({title:e.target.value,error:``})}}
        />
      </label>
      <label>
        <span>${r.fixed?n.sub.date_fixed:n.sub.date}</span>
        <input
          class="sub-date-input"
          type="date"
          .value=${r.fixed?r.max:e.date}
          min=${r.min}
          max=${r.max}
          ?disabled=${e.busy||r.fixed}
          @input=${e=>{this._patchForm({date:e.target.value,error:``})}}
        />
      </label>
      <label>
        <span>${n.sub.minutes}</span>
        <select
          class="sub-minutes-input"
          ?disabled=${e.busy}
          @change=${e=>{let t=e.target.value;this._patchForm({minutes:t===``?null:Number(t),error:``})}}
        >
          <option value="">${n.sub.minutes_none}</option>
          ${Ye(e.minutes,e.storedMinutes).map(t=>C`<option value=${String(t)} ?selected=${e.minutes===t}>${P(t,this._language()===`nl`?`nl`:`en`)}</option>`)}
        </select>
      </label>
      ${e.error?C`<p class="form-error" id=${a} role="alert">${e.error}</p>`:T}
      <div class="form-actions">
        <button type="button" class="cancel" ?disabled=${e.busy} @click=${()=>{this._cancelForm()}}>${n.sub.cancel}</button>
        <button type="submit" class="primary" ?disabled=${e.busy}>${e.busy?n.sub.saving:n.sub.save}</button>
      </div>
    </form>`}_patchForm(e){this._form&&={...this._form,...e}}_openForm(e,t){this._confirm=void 0,this._subConfirm=void 0,this._closeMenu(!1);let n=this._dateBounds(t),r=e.mode===`edit`?t.subtasks?.find(t=>t.uid===e.subUid):void 0;this._form={...e,title:r?.title??``,date:r?this._clampDate(r.planned,n):n.fixed?n.max:n.min,minutes:r?.minutes??null,storedMinutes:r?.minutes??null,error:``,busy:!1},this._focusForm=!0}_cancelForm(){let e=this._form;if(!e||e.busy)return;this._form=void 0;let t=e.mode===`add`?`[data-add-sub="${CSS.escape(e.itemUid)}"]`:`[data-edit="${CSS.escape(e.subUid??``)}"]`;this.updateComplete.then(()=>{this.shadowRoot?.querySelector(t)?.focus()})}_formError(e,t){let n=this._texts().sub.errors;this._form={...e,busy:!1,error:(t?n[t]:void 0)??n.default??``},this._focusForm=!0}async _submitForm(){let e=this._form,t=this._hass,n=this._config?.entity;if(!e||e.busy||!t||!n||!this._payload?.available||this._offline)return;let r=this._items().find(t=>t.uid===e.itemUid);if(!r)return;let i=e.title.trim();if(i===``||i.length>wr){this._formError(e,`invalid_format`);return}let a=this._dateBounds(r);if(e.mode===`add`){let o=a.fixed?a.max:e.date;if(o<a.min||o>a.max){this._formError(e,`invalid_date`);return}this._form={...e,busy:!0,error:``};try{let a=await t.callWS({type:br,entity_id:n,item:r.uid,title:i,date:o,...e.minutes===null?{}:{minutes:e.minutes}}),s=new Set((r.subtasks??[]).map(e=>e.uid)),c=(a.subtasks??[]).filter(e=>!s.has(e.uid)).pop();this._form=void 0,this._pendingFocus=c?.uid??a.subtasks?.at(-1)?.uid}catch(t){this._formError({...e,title:e.title},t?.code)}return}let o=r.subtasks?.find(t=>t.uid===e.subUid);if(!o)return;let s={};if(i!==o.title&&(s.title=i),!a.fixed&&e.date!==this._clampDate(o.planned,a)){if(e.date<a.min||e.date>a.max){this._formError(e,`invalid_date`);return}s.planned=e.date}e.minutes!==(o.minutes??null)&&(s.minutes=e.minutes),s.title===void 0&&s.planned===void 0&&s.minutes===void 0?this._cancelForm():(this._form=void 0,this._focusAfter([`[data-edit="${CSS.escape(o.uid)}"]`]),await this._changeSubtask(o.uid,s,{type:xr,entity_id:n,subtask:o.uid,...s.title===void 0?{}:{title:s.title},...s.planned===void 0?{}:{date:s.planned},...s.minutes===void 0?{}:{minutes:s.minutes}},e))}async _changeSubtask(e,t,n,r){let i=this._hass;if(!i)return;let a=++this._nextToken;this._subTokens.set(e,a),this._subEdits=new Map(this._subEdits).set(e,t);try{if(await i.callWS(n),this._subTokens.get(e)!==a)return;if(this._subTokens.delete(e),ot(this._findSubtask(e),t)){let t=new Map(this._subEdits);t.delete(e),this._subEdits=t}}catch(t){if(this._subTokens.get(e)!==a)return;this._subTokens.delete(e);let n=new Map(this._subEdits);n.delete(e),this._subEdits=n;let i=t?.code;if(r&&!this._form&&this._formTarget(r))this._formError({...r,busy:!1},i);else{let e=this._texts().sub.errors;this._showToast((i?e[i]:void 0)??this._texts().save_failed)}}}_askDeleteSubtask(e){this._form=void 0,this._confirm=void 0,this._subConfirm=e,this.updateComplete.then(()=>{this.shadowRoot?.querySelector(`.subconfirm .cancel`)?.focus()})}_cancelDeleteSubtask(e){this._subConfirm=void 0,this.updateComplete.then(()=>{this.shadowRoot?.querySelector(`[data-delete="${CSS.escape(e)}"]`)?.focus()})}async _deleteSubtask(e){let t=this._config?.entity;if(this._subConfirm=void 0,!t||!this._hass||!this._payload?.available||this._offline)return;let n=this.shadowRoot?.querySelector(`li[data-uid="${CSS.escape(e)}"]`),r=[n?.nextElementSibling,n?.previousElementSibling].map(e=>e?.getAttribute(`data-uid`)).filter(e=>typeof e==`string`);this._focusAfter([...r.map(e=>`li[data-uid="${CSS.escape(e)}"] input[type="checkbox"]`),`[data-add-sub="${CSS.escape(I(e))}"]`,`.add`]),await this._changeSubtask(e,{deleted:!0},{type:Sr,entity_id:t,subtask:e})}_focusAfter(e){this.updateComplete.then(()=>{for(let t of e){let e=this.shadowRoot?.querySelector(t);if(e){e.focus();return}}})}updated(){this._timer.afterRender();let e=this.shadowRoot?.querySelector(`.subform .sub-minutes-input`),t=this._form?.minutes===null?``:String(this._form?.minutes??``);if(e&&this._form&&e.value!==t&&(e.value=t),this._focusForm&&this._form&&(this._focusForm=!1,this.shadowRoot?.querySelector(`.subform .sub-title-input`)?.focus()),this._pendingFocus){let e=this.shadowRoot?.querySelector(`li[data-uid="${CSS.escape(this._pendingFocus)}"] input[type="checkbox"]`);if(e)this._pendingFocus=void 0,e.focus();else if(this._findSubtask(this._pendingFocus)){let e=I(this._pendingFocus);this._pendingFocus=void 0,this.shadowRoot?.querySelector(`[data-add-sub="${CSS.escape(e)}"]`)?.focus()}}}_renderMagisterChip(e,t,n){if(e.info_type===null)return T;let r=e.override??null,i=At(t,e.info_type,e.label??``),a=r?.mode===`replace`?t.override_replaced:t.override_disabled,o=`chip magister ${r?`overridden`:e.info_type>=2?`test`:``}`,s=r?C`<s>${i}</s><span class="sr-only"> ${a}</span>`:C`${i}`;return C`${n?C`<button
          type="button"
          class=${o}
          data-menu-button=${e.uid}
          aria-haspopup="menu"
          aria-expanded=${this._menu===e.uid?`true`:`false`}
          title=${t.override_tip}
          @click=${()=>{this._menu===e.uid?this._closeMenu(!0):this._openMenu(e.uid,`first`)}}
          @keydown=${t=>{this._onChipKey(t,e.uid)}}
        >${s}</button>`:C`<span class=${o}>${s}</span>`}${r?.mode===`replace`?C`<span class="chip manual plain ${r.label.kind===`test`?`test`:``}"
            >${r.label.name}</span
          >`:T}`}_renderMenu(e,t){let n=Et(e,this._payload?.labels??[]),r=(t,n,r)=>C`<button
        type="button"
        role="menuitem"
        tabindex="-1"
        aria-label=${n}
        @click=${()=>{this._choose(e,r)}}
      >${t}</button>`;return C`<div
      class="menu"
      role="menu"
      aria-label=${V(t.override_menu,{subject:e.subject})}
      @keydown=${t=>{this._onMenuKey(t,e.uid)}}
    >
      ${n.replace.length>0?C`<div role="group" aria-label=${t.override_replace_with}>
            <span class="menu-heading" aria-hidden="true">${t.override_replace_with}</span>
            ${n.replace.map(e=>r(e.name,V(t.override_replace_option,{name:e.name}),{mode:`replace`,label:e}))}
          </div>`:T}
      ${n.disable?r(t.override_disable,t.override_disable,{mode:`disable`}):T}
      ${n.restore?r(t.override_restore,t.override_restore,{mode:`clear`}):T}
    </div>`}_renderManualChip(e,t,n,r){return C`<span class="chip manual ${t.kind===`test`?`test`:``}"
      >${t.name}<button
        type="button"
        class="chip-remove"
        data-key=${z(e,t.id)}
        aria-label=${V(n.remove_label,{name:t.name})}
        title=${V(n.remove_label,{name:t.name})}
        ?disabled=${!r}
        @click=${()=>{this._askRemove(e,t)}}
      >×</button></span
    >`}_renderProgress(e,t,n,r){let i=Ie(e.progress),a=j.includes(e.progress);return C`<div class="progress">
      <div
        class="segments"
        role="radiogroup"
        aria-label=${t}
      >
        ${j.map(t=>C`<button
            type="button"
            role="radio"
            class="segment ${t===i?`selected`:``} ${t<i?`below`:``} ${a?``:`between`}"
            aria-checked=${a&&t===i?`true`:`false`}
            aria-label=${V(n.percent,{n:t})}
            tabindex=${t===i?0:-1}
            ?disabled=${!r}
            @click=${()=>{t!==e.progress&&this._setProgress(e.uid,t)}}
            @keydown=${t=>{this._onSegmentKey(t,e.uid,e.progress)}}
          >
            ${t}
          </button>`)}
      </div>
      <span class="percent">${V(n.percent,{n:e.progress})}</span>
    </div>`}_onSegmentKey(e,t,n){let r=j.indexOf(Ie(n)),i;switch(e.key){case`ArrowRight`:case`ArrowDown`:i=Math.min(r+1,j.length-1);break;case`ArrowLeft`:case`ArrowUp`:i=Math.max(r-1,0);break;case`Home`:i=0;break;case`End`:i=j.length-1;break;default:return}e.preventDefault();let a=j[i];if(a===void 0||a===n)return;let o=e.currentTarget;this._setProgress(t,a),this.updateComplete.then(()=>{o.parentElement?.querySelector(`[tabindex="0"]`)?.focus()})}static{this.styles=[gr,o`
    :host {
      display: block;
      /* Subtasks and proposals: one colour. The text variant mixes in the text colour, so it
         keeps its contrast on the light tint (light theme) and on the dark card (dark theme). */
      --sub-color: var(--info-color, #039be5);
      --sub-text: color-mix(in srgb, var(--sub-color) 55%, var(--primary-text-color, #212121));
    }
    ha-card {
      display: block;
      overflow: hidden;
    }
    .content {
      padding: 0 16px 16px;
    }
    .content:not(.titled) {
      padding-top: 12px;
    }
    .state {
      margin: 16px 0;
      text-align: center;
      color: var(--secondary-text-color);
    }
    .state.error {
      color: var(--error-color);
    }
    .state.empty {
      font-size: 1.1em;
      padding: 12px 0;
    }
    .banner {
      margin: 0 0 12px;
      padding: 8px 12px;
      border-radius: 8px;
      background: color-mix(in srgb, var(--warning-color, #ffa600) 20%, transparent);
      color: var(--primary-text-color);
      font-size: 0.9em;
    }
    .bars {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin: 0 0 12px;
    }
    .titled .bars {
      margin-top: 12px;
    }
    .bar-head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 0.9em;
      font-weight: 500;
      color: var(--primary-text-color);
    }
    .bar-value {
      font-variant-numeric: tabular-nums;
    }
    .track {
      height: 8px;
      margin: 4px 0 2px;
      border-radius: 4px;
      overflow: hidden;
      background: var(--divider-color);
    }
    .fill {
      height: 100%;
      border-radius: 4px;
      background: var(--primary-color);
    }
    .bar-note {
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .bars.stale {
      opacity: 0.55;
    }
    .bar.unavailable .bar-head {
      color: var(--secondary-text-color);
    }
    .days.stale {
      opacity: 0.55;
    }
    h3.section {
      margin: 16px 0 0;
      font-size: 0.85em;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--secondary-text-color);
    }
    h4 {
      margin: 16px 0 4px;
      font-size: 1em;
      font-weight: 600;
      color: var(--primary-text-color);
    }
    h4::first-letter {
      text-transform: uppercase;
    }
    h4.today {
      color: var(--primary-color);
    }
    ul {
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .item {
      display: flex;
      gap: 12px;
      padding: 10px 0 10px 8px;
      border-top: 1px solid var(--divider-color);
      border-left: 3px solid transparent;
    }
    .item:first-child {
      border-top: none;
    }
    .item.test {
      border-left-color: var(--warning-color, #ffa600);
      background: color-mix(in srgb, var(--warning-color, #ffa600) 8%, transparent);
    }
    .item.subtask {
      border-left-color: var(--sub-color);
      background: color-mix(in srgb, var(--sub-color) 10%, transparent);
    }
    .item.done .subject,
    .item.done .text {
      color: var(--secondary-text-color);
      text-decoration: line-through;
    }
    input[type="checkbox"] {
      flex: none;
      width: 22px;
      height: 22px;
      margin: 2px 0 0;
      accent-color: var(--primary-color);
      cursor: pointer;
    }
    input[type="checkbox"]:disabled {
      cursor: default;
    }
    .main {
      flex: 1;
      min-width: 0;
    }
    .head {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 4px 8px;
    }
    .subject {
      font-weight: 500;
      color: var(--primary-text-color);
      overflow-wrap: anywhere;
    }
    .item.test .subject {
      font-weight: 700;
    }
    .chip {
      padding: 1px 8px;
      border-radius: 10px;
      font-size: 0.75em;
      font-weight: 500;
      background: var(--secondary-background-color);
      color: var(--secondary-text-color);
      border: 1px solid var(--divider-color);
    }
    .chip.test {
      font-weight: 700;
      color: var(--text-primary-color, #fff);
      background: var(--warning-color, #ffa600);
      border-color: var(--warning-color, #ffa600);
    }
    .chip.manual {
      display: inline-flex;
      align-items: center;
      gap: 2px;
      padding-right: 2px;
      background: transparent;
      color: var(--primary-color);
      border: 1.5px solid var(--primary-color);
    }
    button.chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      min-height: 28px;
      font: inherit;
      font-size: 0.75em;
      font-weight: 500;
      cursor: pointer;
    }
    button.chip.test {
      font-weight: 700;
    }
    button.chip::after {
      content: "\\25be";
      content: "\\25be" / "";
      font-size: 0.9em;
      opacity: 0.8;
    }
    .chip.overridden {
      font-weight: 500;
      color: var(--secondary-text-color);
      background: var(--secondary-background-color);
      border-color: var(--divider-color);
    }
    .chip.overridden s {
      text-decoration: line-through;
    }
    .chip.manual.plain {
      padding-right: 8px;
    }
    .menu {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: 2px;
      margin-top: 6px;
      padding: 4px;
      max-width: 320px;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      background: var(--card-background-color, var(--ha-card-background, #fff));
    }
    .menu [role="group"] {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .menu-heading {
      padding: 4px 8px 0;
      font-size: 0.75em;
      color: var(--secondary-text-color);
    }
    .menu [role="menuitem"] {
      min-height: 40px;
      padding: 0 12px;
      border: none;
      border-radius: 6px;
      background: transparent;
      color: var(--primary-text-color);
      font: inherit;
      font-size: 0.9em;
      text-align: left;
      cursor: pointer;
    }
    .menu [role="menuitem"]:hover,
    .menu [role="menuitem"]:focus-visible {
      background: color-mix(in srgb, var(--primary-color) 14%, transparent);
    }
    .menu [role="menuitem"]:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: -2px;
    }
    .item.disabled .subject,
    .item.disabled .percent {
      opacity: 0.7;
    }
    .chip.manual.test {
      color: var(--warning-color, #ffa600);
      border-color: var(--warning-color, #ffa600);
      background: transparent;
    }
    .chip-remove {
      min-width: 24px;
      min-height: 24px;
      padding: 0;
      border: none;
      border-radius: 50%;
      background: none;
      color: inherit;
      font: inherit;
      font-size: 1.2em;
      line-height: 1;
      cursor: pointer;
    }
    .chip-remove:disabled {
      cursor: default;
      opacity: 0.5;
    }
    .note {
      margin: 4px 0 0;
      font-size: 0.9em;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: var(--secondary-text-color);
    }
    .note-label {
      font-weight: 500;
      color: var(--primary-text-color);
    }
    .confirm {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-top: 6px;
      padding: 6px 8px;
      border-radius: 8px;
      background: color-mix(in srgb, var(--error-color) 12%, transparent);
      font-size: 0.9em;
    }
    .confirm button,
    .switch,
    .add {
      min-height: 36px;
      padding: 0 12px;
      border-radius: 18px;
      border: 1px solid var(--divider-color);
      background: transparent;
      color: var(--primary-text-color);
      font: inherit;
      font-size: 0.85em;
      cursor: pointer;
    }
    .confirm .danger {
      border-color: var(--error-color);
      background: var(--error-color);
      color: var(--text-primary-color, #fff);
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin: 0 0 12px;
    }
    .switch.on {
      border-color: var(--primary-color);
      background: color-mix(in srgb, var(--primary-color) 18%, transparent);
      color: var(--primary-color);
      font-weight: 500;
    }
    .switch .tick {
      display: inline-block;
      min-width: 1em;
    }
    .add {
      margin-left: auto;
      min-width: 36px;
      padding: 0;
      font-size: 1.4em;
      line-height: 1;
      border-color: var(--primary-color);
      color: var(--primary-color);
    }
    .meta {
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .attachments svg {
      width: 16px;
      height: 16px;
      vertical-align: middle;
      fill: currentColor;
    }
    .badge {
      padding: 1px 8px;
      border-radius: 10px;
      font-size: 0.75em;
      font-weight: 500;
      color: var(--error-color);
      border: 1px solid var(--error-color);
    }
    .ai-badge {
      flex: 0 0 auto;
      padding: 0 6px;
      border-radius: 10px;
      font-size: 0.7em;
      font-weight: 600;
      line-height: 1.6;
      letter-spacing: 0.04em;
      color: var(--primary-color);
      border: 1px solid var(--primary-color);
    }
    .parent-badge {
      color: var(--secondary-text-color);
      border-color: var(--secondary-text-color);
    }
    .sub-minutes {
      flex: 0 0 auto;
      font-size: 0.85em;
      color: var(--secondary-text-color);
      white-space: nowrap;
    }
    .day-head {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      column-gap: 12px;
    }
    .planned {
      font-size: 0.85em;
      color: var(--secondary-text-color);
    }
    .planned.adjusted {
      text-decoration: underline dotted;
      text-underline-offset: 3px;
    }
    .planned.over {
      padding: 0 8px;
      border: 1px solid var(--warning-color, #ffa600);
      border-radius: 10px;
      background: color-mix(in srgb, var(--warning-color, #ffa600) 15%, transparent);
      color: var(--primary-text-color);
      font-weight: 600;
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
    }
    .text {
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
      line-clamp: 2;
      overflow: hidden;
      width: 100%;
      margin: 4px 0 0;
      padding: 0;
      border: none;
      background: none;
      font: inherit;
      font-size: 0.9em;
      text-align: left;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: var(--secondary-text-color);
      cursor: pointer;
    }
    .text.expanded {
      display: block;
      -webkit-line-clamp: unset;
      line-clamp: unset;
      overflow: visible;
    }
    .progress {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 8px;
    }
    .segments {
      display: flex;
      flex: 0 1 260px;
      min-width: 0;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      overflow: hidden;
    }
    .segment {
      flex: 1;
      min-width: 0;
      min-height: 36px;
      padding: 0;
      border: none;
      border-left: 1px solid var(--divider-color);
      background: transparent;
      color: var(--secondary-text-color);
      font: inherit;
      font-size: 0.8em;
      cursor: pointer;
    }
    .segment:first-child {
      border-left: none;
    }
    .segment.below {
      background: color-mix(in srgb, var(--primary-color) 22%, transparent);
    }
    .segment.between.selected {
      background: color-mix(in srgb, var(--primary-color) 55%, transparent);
    }
    .segment.selected {
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
      font-weight: 700;
    }
    .segment:disabled {
      cursor: default;
    }
    .segment:focus-visible,
    .text:focus-visible,
    input[type="checkbox"]:focus-visible,
    .toast button:focus-visible,
    .confirm button:focus-visible,
    .proposal button:focus-visible,
    .chip-remove:focus-visible,
    button.chip:focus-visible,
    .switch:focus-visible,
    .add:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
    .percent {
      font-size: 0.8em;
      min-width: 3.2em;
      color: var(--secondary-text-color);
    }
    .toast {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin: 0 16px 16px;
      padding: 8px 12px;
      border-radius: 8px;
      background: var(--error-color);
      color: var(--text-primary-color, #fff);
      font-size: 0.9em;
    }
    .toast button {
      border: none;
      background: none;
      color: inherit;
      font: inherit;
      font-weight: 700;
      text-decoration: underline;
      cursor: pointer;
    }
    h4.overdue {
      color: var(--error-color);
    }
    .arrow {
      color: var(--sub-text);
    }
    .sub-marker {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      flex: 0 0 auto;
      padding: 0 7px 0 4px;
      border-radius: 10px;
      border: 1px solid color-mix(in srgb, var(--sub-color) 60%, transparent);
      background: color-mix(in srgb, var(--sub-color) 12%, transparent);
      color: var(--sub-text);
      font-size: 0.75em;
      font-weight: 500;
      line-height: 1.6;
      white-space: nowrap;
    }
    .sub-marker svg {
      width: 14px;
      height: 14px;
      fill: currentColor;
    }
    .proposals {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 0 0 12px;
    }
    .proposal {
      padding: 8px 12px;
      border-left: 3px solid var(--sub-color);
      border-radius: 4px 8px 8px 4px;
      background: color-mix(in srgb, var(--sub-color) 10%, transparent);
    }
    .proposal-text {
      margin: 0 0 8px;
      overflow-wrap: anywhere;
    }
    .proposal-title {
      font-weight: 600;
      color: var(--sub-text);
    }
    .nowrap {
      white-space: nowrap;
    }
    .proposal-expires {
      display: block;
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .proposal-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .proposal-actions button {
      min-height: 36px;
      padding: 0 14px;
      border-radius: 18px;
      border: 1px solid var(--divider-color);
      background: transparent;
      color: var(--primary-text-color);
      font: inherit;
      font-size: 0.85em;
      cursor: pointer;
    }
    .proposal .primary {
      border-color: var(--primary-color);
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    .proposal button:disabled {
      cursor: default;
      opacity: 0.6;
    }
    .proposal .confirm {
      margin-top: 0;
      background: color-mix(in srgb, var(--sub-color) 16%, transparent);
    }
    .proposed-max {
      font-size: 0.85em;
      color: var(--sub-text);
      font-weight: 500;
    }
    .closed-proposals {
      margin-top: 8px;
    }
    .closed-proposal {
      display: flex;
      flex-wrap: wrap;
      gap: 2px 8px;
      padding: 6px 0 6px 8px;
      border-left: 3px solid var(--sub-color);
      font-size: 0.9em;
      color: var(--secondary-text-color);
      overflow-wrap: anywhere;
    }
    .proposal-status {
      font-weight: 600;
      color: var(--sub-text);
    }
    .item.subtask {
      padding-left: 24px;
      padding-right: 8px;
    }
    .item.overdue .ref {
      color: var(--error-color);
    }
    .ref {
      overflow-wrap: anywhere;
    }
    .progress.derived {
      flex-wrap: wrap;
      padding-right: 8px;
      row-gap: 2px;
    }
    .progress.derived .track {
      flex: 1 1 120px;
      max-width: 260px;
      margin: 0;
    }
    .sub-actions {
      display: inline-flex;
      margin-left: auto;
      white-space: nowrap;
    }
    .sub-title {
      flex: 1 1 8em;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .sub-count {
      flex: 0 1 auto;
      min-width: 0;
    }
    .icon-btn,
    button.link {
      min-height: 32px;
      min-width: 32px;
      padding: 0 6px;
      border: none;
      background: none;
      color: var(--primary-color);
      font: inherit;
      font-size: 0.85em;
      cursor: pointer;
    }
    .icon-btn {
      color: var(--secondary-text-color);
    }
    button.link {
      display: block;
      margin-top: 4px;
      padding: 0;
    }
    .icon-btn:focus-visible,
    button.link:focus-visible,
    .subform button:focus-visible,
    .subform input:focus-visible,
    .subform select:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
    .subform {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 6px;
      padding: 8px;
      max-width: 360px;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
    }
    .subform label {
      display: flex;
      flex-direction: column;
      gap: 2px;
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .subform input,
    .subform select {
      min-height: 36px;
      padding: 0 8px;
      border: 1px solid var(--divider-color);
      border-radius: 6px;
      background: transparent;
      color: var(--primary-text-color);
      font: inherit;
      font-size: 1.1em;
    }
    .form-error {
      margin: 0;
      font-size: 0.85em;
      color: var(--error-color);
    }
    .form-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
    }
    .form-actions button {
      min-height: 36px;
      padding: 0 14px;
      border-radius: 18px;
      border: 1px solid var(--divider-color);
      background: transparent;
      color: var(--primary-text-color);
      font: inherit;
      font-size: 0.85em;
      cursor: pointer;
    }
    .form-actions .primary {
      border-color: var(--primary-color);
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    .form-actions button:disabled {
      cursor: default;
      opacity: 0.6;
    }
    @media (max-width: 480px) {
      .segments {
        flex: 1 1 auto;
      }
      .segment {
        min-height: 40px;
      }
    }
    .timer-bar {
      margin: 0 0 12px;
      padding: 8px 12px 10px;
      border-left: 3px solid var(--timer-color);
      border-radius: 4px 8px 8px 4px;
      background: color-mix(in srgb, var(--timer-color) 10%, transparent);
    }
    .timer-bar.finished {
      border-left-color: var(--timer-warn);
      background: color-mix(in srgb, var(--timer-warn) 14%, transparent);
    }
    .timer-bar-row,
    .timer-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px 10px;
    }
    .timer-bar-text {
      display: flex;
      flex: 1 1 10em;
      flex-direction: column;
      min-width: 0;
    }
    .timer-bar-title {
      font-weight: 600;
      overflow-wrap: anywhere;
    }
    .bar-countdown {
      font-size: 1.5em;
    }
    .timer-row {
      margin-top: 6px;
    }
    .timer-state {
      padding: 0 8px;
      border-radius: 10px;
      border: 1px solid var(--divider-color);
      font-size: 0.8em;
      font-weight: 500;
      color: var(--secondary-text-color);
    }
    .timer-state.finished {
      border-color: var(--timer-warn);
      color: var(--primary-text-color);
      font-weight: 700;
    }
    .timer-settings-btn {
      margin-left: auto;
    }
    .timer-settings-btn + .add {
      margin-left: 0;
    }
  `]}},kr=6e3,Ar=52,jr=2*Math.PI*Ar;function Mr(e){if(!e||typeof e!=`object`)throw Error(`Invalid configuration`);let t=e.entity??``;if(typeof t!=`string`)throw Error(`entity must be a to-do entity id`);if(t!==``&&!t.startsWith(`todo.`))throw Error(`entity must be a to-do entity (todo.*)`);return{entity:t,title:typeof e.title==`string`?e.title:``,show_when_idle:e.show_when_idle!==!1}}var Nr=class extends A{static{this.properties={_payload:{state:!0},_loadError:{state:!0},_offline:{state:!0},_toast:{state:!0}}}set preview(e){this._preview=e===!0,this.requestUpdate()}get preview(){return this._preview}set editMode(e){this._editMode=e===!0,this.requestUpdate()}get editMode(){return this._editMode}constructor(){super(),this._preview=!1,this._editMode=!1,this._hassKey=``,this.connectedWhileHidden=!0,this._offline=!1,this._toast=``,this._subscription=new Ht({isConnected:()=>this.isConnected,hass:()=>this._hass,entity:()=>this._config?.entity,onPayload:e=>{this._payload=e,this._loadError=void 0,this._offline=!1,this._timer.onPayload()},onLoadError:e=>{this._loadError=e},onOffline:e=>{this._offline=e},hasLoadError:()=>this._loadError!==void 0}),this._timer=new qn(this,{hass:()=>this._hass,entity:()=>this._config?.entity,payload:()=>this._payload,canWrite:()=>this._payload?.available===!0&&!this._offline,texts:()=>this._texts(),showError:e=>{this._showToast(e)},itemLabel:e=>an(e,this._texts()),fallbackFocus:()=>[`.timer-idle`],lockOnDenied:!0})}static getConfigElement(){return document.createElement(`magister-timer-card-editor`)}static getStubConfig(e){return{entity:Object.entries(e?.entities??{}).find(([e,t])=>e.startsWith(`todo.`)&&t?.platform===`magister`)?.[0]??``}}setConfig(e){let t=Mr(e);t.entity!==this._config?.entity&&(this._subscription.reset(),this._payload=void 0,this._loadError=void 0,this._offline=!1,this._timer.reset(),this._subscription.resetBackoff()),this._config=t,this.requestUpdate(),this._subscription.ensure()}set hass(e){this._hass=e;let t=`${e?.locale?.language??``}|${e?.language??``}`;t===this._hassKey&&this._payload||(this._hassKey=t,this.requestUpdate()),this._subscription.ensure()}get hass(){return this._hass}getCardSize(){return this._hidden()?0:this._timer.view()?4:2}getGridOptions(){return{columns:6,min_columns:3,min_rows:2}}connectedCallback(){super.connectedCallback(),this._subscription.ensure(),this._timer.connected()}disconnectedCallback(){super.disconnectedCallback(),this._subscription.reset(),this._timer.disconnected(),this._toastTimer&&clearTimeout(this._toastTimer)}_texts(){return B(this._hass?.locale?.language??this._hass?.language)}_showToast(e){this._toast=e,this._toastTimer&&clearTimeout(this._toastTimer),this._toastTimer=setTimeout(()=>{this._toast=``},kr)}_hidden(){return this._config?.show_when_idle!==!1||!this._config.entity||this._loadError||this._preview||this._editMode?!1:this._timer.view()===void 0}willUpdate(){this._timer.willUpdate();let e=this._hidden();e!==this.hasAttribute(`hidden`)&&(this.toggleAttribute(`hidden`,e),this.dispatchEvent(new CustomEvent(`card-visibility-changed`,{detail:{value:!e},bubbles:!0,composed:!0})))}_context(e){return{controller:this._timer,texts:e,language:kt(this._hass?.locale?.language??this._hass?.language),enabled:this._payload?.available===!0&&!this._offline}}render(){if(this._hidden())return T;let e=this._texts();return C`<ha-card .header=${this._config?.title??``}>
      ${ar(this._context(e))}
      <div class="content ${this._config?.title?`titled`:``}">${this._renderBody(e)}${this._renderNotify(e)}</div>
      ${this._toast?C`<div class="toast" role="alert">
            <span>${this._toast}</span>
            <button type="button" @click=${()=>{this._toast=``}}>${e.dismiss}</button>
          </div>`:T}
    </ha-card>`}_renderNotify(e){return!this._config?.entity||this._loadError||!this._payload?T:mr(this._context(e),this._timer.notifyOpen,()=>{this._timer.notifyOpen=!this._timer.notifyOpen,this.requestUpdate();let e=this._timer.notifyOpen?[`.notify-panel input`,`.notify-panel`]:[`[data-notify-button]`];this.updateComplete.then(()=>{for(let t of e){let e=this.shadowRoot?.querySelector(t);if(e){e.focus();return}}})})}_renderBody(e){if(!this._config?.entity)return C`<p class="state">${e.choose_entity}</p>`;if(this._loadError)return C`<p class="state error">${e[this._loadError]}</p>`;if(!this._payload)return C`<p class="state">${e.loading}</p>`;let t=this._payload.available?this._offline?C`<p class="banner" role="status">${e.offline}</p>`:T:C`<p class="banner" role="status">${e.unavailable}</p>`,n=this._context(e),r=this._timer.view();if(!r)return C`${t}<p class="state timer-idle" tabindex="-1">${e.timer.idle}</p>`;let i=n.language===`nl`?`nl`:`en-GB`,a=on(e.timer.meta,{subject:r.timer.subject,label:this._timer.labelOf(r.timer.subtask),date:L(r.timer.due,i)}),o=e.timer[r.state],s=jr*(1-r.fraction),c=r.remaining>=3600;return C`${t}<div class="tc ${r.state}" role="group" aria-label=${e.timer.region}>
      <div class="ring">
        <svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">
          <circle class="ring-track" cx="60" cy="60" r=${Ar}></circle>
          <circle
            class="ring-fill"
            cx="60"
            cy="60"
            r=${Ar}
            stroke-dasharray=${jr.toFixed(2)}
            stroke-dashoffset=${s.toFixed(2)}
            transform="rotate(-90 60 60)"
          ></circle>
        </svg>
        <div class="ring-text">
          <span class="big ${c?`long`:``} countdown ${r.state}" role="timer" aria-live="off"
            ><span class="sr-only">${V(e.timer.countdown_aria,{title:r.timer.title,state:o})}: </span
            >${qt(r.remaining)}</span
          >
          <span class="state-name ${r.state}">${o}</span>
        </div>
      </div>
      <h3 class="tc-title">${r.timer.title}</h3>
      <p class="meta tc-meta">${a}</p>
      <div class="tc-actions">${cr(n,r,`card`)}</div>
      ${this._timer.locked?C`<p class="read-only" role="note">${this._timer.lockCode===`unauthorized`?e.timer.errors.unauthorized:e.timer.read_only}</p>`:T}
      ${lr(n)}
    </div>`}static{this.styles=[gr,o`
      :host {
        display: block;
      }
      :host([hidden]) {
        display: none;
      }
      ha-card {
        display: block;
        overflow: hidden;
      }
      .content {
        padding: 16px;
      }
      .content.titled {
        padding-top: 0;
      }
      .state {
        margin: 16px 0;
        text-align: center;
        color: var(--secondary-text-color);
        font-size: 1.1em;
      }
      .state.error {
        color: var(--error-color);
      }
      .timer-idle:focus {
        outline: none;
      }
      .banner {
        margin: 0 0 12px;
        padding: 8px 12px;
        border-radius: 8px;
        background: color-mix(in srgb, var(--warning-color, #ffa600) 20%, transparent);
        color: var(--primary-text-color);
        font-size: 0.9em;
      }
      .tc {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 6px;
        text-align: center;
      }
      .ring {
        position: relative;
        width: min(240px, 70%);
        aspect-ratio: 1;
      }
      .ring svg {
        display: block;
        width: 100%;
        height: 100%;
      }
      .ring circle {
        fill: none;
        stroke-width: 9;
      }
      .ring-track {
        stroke: var(--divider-color);
      }
      .ring-fill {
        stroke: var(--timer-color);
        stroke-linecap: round;
      }
      .tc.paused .ring-fill {
        stroke: var(--secondary-text-color);
      }
      .tc.finished .ring-fill {
        stroke: var(--timer-warn);
      }
      .ring-text {
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 2px;
      }
      .big {
        font-size: 2.6em;
        line-height: 1.1;
      }
      .big.long {
        font-size: 2em;
      }
      .state-name {
        font-size: 0.95em;
        font-weight: 500;
        color: var(--secondary-text-color);
      }
      .state-name.finished {
        color: var(--primary-text-color);
        font-weight: 700;
      }
      .tc-title {
        margin: 8px 0 0;
        font-size: 1.3em;
        font-weight: 600;
        overflow-wrap: anywhere;
      }
      .tc-meta {
        margin: 0;
        font-size: 0.95em;
        color: var(--secondary-text-color);
      }
      .tc-actions {
        display: flex;
        justify-content: center;
        margin-top: 8px;
      }
      .tc-actions .timer-actions {
        justify-content: center;
        gap: 12px;
      }
      .read-only {
        margin: 8px 0 0;
        padding: 8px 12px;
        border-radius: 8px;
        background: color-mix(in srgb, var(--timer-color) 10%, transparent);
        font-size: 0.9em;
        color: var(--primary-text-color);
      }
      .timer-panel {
        align-self: stretch;
        text-align: left;
      }
      .step {
        min-height: 56px;
        font-size: 1.1em;
      }
      .steps {
        max-width: none;
      }
      .timer-panel-actions button {
        min-height: 52px;
        padding: 0 20px;
        border-radius: 26px;
      }
      .toast {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin: 0 16px 16px;
        padding: 8px 12px;
        border-radius: 8px;
        background: var(--error-color);
        color: var(--text-primary-color, #fff);
        font-size: 0.9em;
      }
      .toast button {
        border: none;
        background: none;
        color: inherit;
        font: inherit;
        font-weight: 700;
        text-decoration: underline;
        cursor: pointer;
      }
      .toast button:focus-visible {
        outline: 2px solid var(--text-primary-color, #fff);
        outline-offset: 2px;
      }
      .meta {
        font-size: 0.8em;
      }
    `]}};function Pr(){return[{name:`entity`,required:!0,selector:{entity:{filter:{domain:`todo`,integration:`magister`}}}},{name:`title`,selector:{text:{}}},{name:`show_when_idle`,selector:{boolean:{}}}]}function Fr(e){return{entity:e.entity??``,title:e.title??``,show_when_idle:e.show_when_idle!==!1}}function Ir(e,t){let n={...e,type:e.type??`custom:magister-timer-card`,entity:typeof t.entity==`string`?t.entity:e.entity??``},r=t.title;return typeof r==`string`&&r.trim()!==``?n.title=r:delete n.title,t.show_when_idle===!1?n.show_when_idle=!1:delete n.show_when_idle,n}var Lr=class extends A{constructor(...e){super(...e),this._computeLabel=e=>this._texts().editor[e.name]??e.name,this._valueChanged=e=>{if(e.stopPropagation(),!this._config)return;let t=Ir(this._config,e.detail.value);this._config=t,this.dispatchEvent(new CustomEvent(`config-changed`,{detail:{config:t},bubbles:!0,composed:!0}))}}static{this.properties={hass:{attribute:!1},_config:{state:!0}}}setConfig(e){this._config=e}_texts(){return B(this.hass?.locale?.language??this.hass?.language)}render(){return this._config?C`<ha-form
      .hass=${this.hass}
      .data=${Fr(this._config)}
      .schema=${Pr()}
      .computeLabel=${this._computeLabel}
      @value-changed=${this._valueChanged}
    ></ha-form>`:T}};customElements.get(`magister-homework-card`)||customElements.define(`magister-homework-card`,Or),customElements.get(`magister-label-dialog`)||customElements.define(`magister-label-dialog`,Lt),customElements.get(`magister-homework-card-editor`)||customElements.define(`magister-homework-card-editor`,Pt),customElements.get(`magister-timer-card`)||customElements.define(`magister-timer-card`,Nr),customElements.get(`magister-timer-card-editor`)||customElements.define(`magister-timer-card-editor`,Lr),window.customCards=window.customCards??[],window.customCards.some(e=>e.type===`magister-homework-card`)||window.customCards.push({type:`magister-homework-card`,name:`Magister Homework planner`,description:`Homework and tests of one child from Magister, with progress per item. / Huiswerk en toetsen van één kind uit Magister, met voortgang per onderdeel.`,preview:!0,documentationURL:`https://github.com/michielmj/ha_magister`}),window.customCards.some(e=>e.type===`magister-timer-card`)||window.customCards.push({type:`magister-timer-card`,name:`Magister Study timer`,description:`The study timer of one child: countdown, pause, stop and progress. / De studietimer van één kind: aftellen, pauzeren, stoppen en voortgang.`,preview:!0,documentationURL:`https://github.com/michielmj/ha_magister`});export{Or as MagisterHomeworkCard,Pt as MagisterHomeworkCardEditor,Nr as MagisterTimerCard,Lr as MagisterTimerCardEditor};