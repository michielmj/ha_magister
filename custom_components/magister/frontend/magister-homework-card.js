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
var e=globalThis,t=e.ShadowRoot&&(e.ShadyCSS===void 0||e.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,n=Symbol(),r=/* @__PURE__ */ new WeakMap,i=class{constructor(e,t,r){if(this._$cssResult$=!0,r!==n)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,n=this.t;if(t&&e===void 0){let t=n!==void 0&&n.length===1;t&&(e=r.get(n)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),t&&r.set(n,e))}return e}toString(){return this.cssText}},a=e=>new i(typeof e==`string`?e:e+``,void 0,n),o=(e,...t)=>new i(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,n),s=(n,r)=>{if(t)n.adoptedStyleSheets=r.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let t of r){let r=document.createElement(`style`),i=e.litNonce;i!==void 0&&r.setAttribute(`nonce`,i),r.textContent=t.cssText,n.appendChild(r)}},c=t?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return a(t)})(e):e,{is:l,defineProperty:u,getOwnPropertyDescriptor:d,getOwnPropertyNames:ee,getOwnPropertySymbols:te,getPrototypeOf:ne}=Object,f=globalThis,p=f.trustedTypes,re=p?p.emptyScript:``,ie=f.reactiveElementPolyfillSupport,m=(e,t)=>e,h={toAttribute(e,t){switch(t){case Boolean:e=e?re:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},g=(e,t)=>!l(e,t),_={attribute:!0,type:String,converter:h,reflect:!1,useDefault:!1,hasChanged:g};Symbol.metadata??=Symbol(`metadata`),f.litPropertyMetadata??=/* @__PURE__ */ new WeakMap;var v=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=_){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&u(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=d(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??_}static _$Ei(){if(this.hasOwnProperty(m(`elementProperties`)))return;let e=ne(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(m(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(m(`properties`))){let e=this.properties,t=[...ee(e),...te(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=/* @__PURE__ */ new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(c(e))}else e!==void 0&&t.push(c(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=/* @__PURE__ */ new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=/* @__PURE__ */ new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=/* @__PURE__ */ new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return s(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?h:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?h:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??g)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=/* @__PURE__ */ new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=/* @__PURE__ */ new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=/* @__PURE__ */ new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};v.elementStyles=[],v.shadowRootOptions={mode:`open`},v[m(`elementProperties`)]=/* @__PURE__ */ new Map,v[m(`finalized`)]=/* @__PURE__ */ new Map,ie?.({ReactiveElement:v}),(f.reactiveElementVersions??=[]).push(`2.1.2`);var y=globalThis,ae=e=>e,b=y.trustedTypes,x=b?b.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,S=`$lit$`,C=`lit$${Math.random().toFixed(9).slice(2)}$`,w=`?`+C,oe=`<${w}>`,T=document,E=()=>T.createComment(``),D=e=>e===null||typeof e!=`object`&&typeof e!=`function`,O=Array.isArray,se=e=>O(e)||typeof e?.[Symbol.iterator]==`function`,k=`[ 	
\f\r]`,A=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,ce=/-->/g,le=/>/g,j=RegExp(`>|${k}(?:([^\\s"'>=/]+)(${k}*=${k}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),ue=/'/g,de=/"/g,M=/^(?:script|style|textarea|title)$/i,N=(e=>(t,...n)=>({_$litType$:e,strings:t,values:n}))(1),P=Symbol.for(`lit-noChange`),F=Symbol.for(`lit-nothing`),I=/* @__PURE__ */ new WeakMap,L=T.createTreeWalker(T,129);function R(e,t){if(!O(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return x===void 0?t:x.createHTML(t)}var fe=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=A;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===A?c[1]===`!--`?o=ce:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=j):(M.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=j):o=le:o===j?c[0]===`>`?(o=i??A,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?j:c[3]===`"`?de:ue):o===de||o===ue?o=j:o===ce||o===le?o=A:(o=j,i=void 0);let d=o===j&&e[t+1].startsWith(`/>`)?` `:``;a+=o===A?n+oe:l>=0?(r.push(s),n.slice(0,l)+S+n.slice(l)+C+d):n+C+(l===-2?t:d)}return[R(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},z=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=fe(t,n);if(this.el=e.createElement(l,r),L.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=L.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(S)){let t=u[o++],n=i.getAttribute(e).split(C),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?me:r[1]===`?`?he:r[1]===`@`?ge:H}),i.removeAttribute(e)}else e.startsWith(C)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(M.test(i.tagName)){let e=i.textContent.split(C),t=e.length-1;if(t>0){i.textContent=b?b.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],E()),L.nextNode(),c.push({type:2,index:++a});i.append(e[t],E())}}}else if(i.nodeType===8){if(i.data===w)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(C,e+1))!==-1;)c.push({type:7,index:a}),e+=C.length-1}}a++}}static createElement(e,t){let n=T.createElement(`template`);return n.innerHTML=e,n}};function B(e,t,n=e,r){if(t===P)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=D(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=B(e,i._$AS(e,t.values),i,r)),t}var pe=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??T).importNode(t,!0);L.currentNode=r;let i=L.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new V(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new _e(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=L.nextNode(),a++)}return L.currentNode=T,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},V=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=F,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=B(this,e,t),D(e)?e===F||e==null||e===``?(this._$AH!==F&&this._$AR(),this._$AH=F):e!==this._$AH&&e!==P&&this._(e):e._$litType$===void 0?e.nodeType===void 0?se(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==F&&D(this._$AH)?this._$AA.nextSibling.data=e:this.T(T.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=z.createElement(R(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new pe(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=I.get(e.strings);return t===void 0&&I.set(e.strings,t=new z(e)),t}k(t){O(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(E()),this.O(E()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=ae(e).nextSibling;ae(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},H=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=F,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(/* @__PURE__ */ new String),this.strings=n):this._$AH=F}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=B(this,e,t,0),a=!D(e)||e!==this._$AH&&e!==P,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=B(this,r[n+o],t,o),s===P&&(s=this._$AH[o]),a||=!D(s)||s!==this._$AH[o],s===F?e=F:e!==F&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===F?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},me=class extends H{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===F?void 0:e}},he=class extends H{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==F)}},ge=class extends H{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=B(this,e,t,0)??F)===P)return;let n=this._$AH,r=e===F&&n!==F||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==F&&(n===F||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},_e=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){B(this,e)}},ve=y.litHtmlPolyfillSupport;ve?.(z,V),(y.litHtmlVersions??=[]).push(`3.3.3`);var ye=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new V(t.insertBefore(E(),e),e,void 0,n??{})}return i._$AI(e),i},U=globalThis,W=class extends v{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=ye(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return P}};W._$litElement$=!0,W.finalized=!0,U.litElementHydrateSupport?.({LitElement:W});var be=U.litElementPolyfillSupport;be?.({LitElement:W}),(U.litElementVersions??=[]).push(`4.2.2`);var G=[0,25,50,75,100];function K(e){return Number.isFinite(e)?Math.min(Math.round(Math.min(Math.max(e,0),100)/25)*25,100):0}function xe(e){if(!e.completed)return 100;let t=Math.round(e.last_partial);return Math.min(Math.max(Number.isFinite(t)?t:0,0),99)}var q=/^(\d{4})-(\d{2})-(\d{2})$/;function J(e){let t=q.exec(e);return t?new Date(Date.UTC(Number(t[1]),Number(t[2])-1,Number(t[3]))):/* @__PURE__ */ new Date(NaN)}function Y(e,t){let n=J(e);return n.setUTCDate(n.getUTCDate()+t),n.toISOString().slice(0,10)}function Se(e,t){try{let n=new Intl.DateTimeFormat(`en-CA`,{timeZone:t,year:`numeric`,month:`2-digit`,day:`2-digit`}).format(e);if(q.test(n))return n}catch{}return(/* @__PURE__ */ new Date(e.getTime()-e.getTimezoneOffset()*6e4)).toISOString().slice(0,10)}function Ce(e,t){let n=J(e);return Number.isNaN(n.getTime())?e:new Intl.DateTimeFormat(t,{timeZone:`UTC`,weekday:`long`,day:`numeric`,month:`long`}).format(n)}function we(e,t){let n=Y(t.today,t.daysAhead);return e.filter(e=>e.completed&&!t.showCompleted&&!t.keep?.has(e.uid)?!1:e.date<t.today?t.showPast:e.date<=n)}function Te(e,t){return e<t?`past`:e===t?`today`:e===Y(t,1)?`tomorrow`:`future`}function Ee(e,t){let n=/* @__PURE__ */ new Map;for(let r of e){let e=n.get(r.date);e||(e={date:r.date,kind:Te(r.date,t),items:[]},n.set(r.date,e)),e.items.push(r)}return[...n.values()].sort((e,t)=>e.date.localeCompare(t.date))}function De(e,t){let n=e.last_partial;return t<100?n=t:e.progress<100&&(n=e.progress),{progress:t,completed:t>=100,last_partial:n}}function Oe(e,t){return t.size===0?[...e]:e.map(e=>{let n=t.get(e.uid);return n?{...e,...n}:e})}var X=[{period:`next_day`,option:`show_progress_tomorrow`},{period:`week`,option:`show_progress_week`},{period:`next_week`,option:`show_progress_next_week`}];function ke(e){let t=Number.isFinite(e.value)?e.value:0;return Math.min(Math.max(Math.round(t),0),100)}function Ae(e){if(!e||typeof e!=`object`)throw Error(`Invalid configuration`);let t=e.entity??``;if(typeof t!=`string`)throw Error(`entity must be a to-do entity id`);if(t!==``&&!t.startsWith(`todo.`))throw Error(`entity must be a to-do entity (todo.*)`);let n=e.days_ahead??7;if(typeof n!=`number`||!Number.isFinite(n)||n<0)throw Error(`days_ahead must be a number of days (0 or more)`);return{entity:t,show_completed:e.show_completed===!0,show_past:e.show_past===!0,days_ahead:Math.min(Math.floor(n),365),show_progress_tomorrow:e.show_progress_tomorrow===!0,show_progress_week:e.show_progress_week===!0,show_progress_next_week:e.show_progress_next_week===!0,title:typeof e.title==`string`?e.title:``,language:e.language===`nl`||e.language===`en`?e.language:`auto`,card_id:typeof e.card_id==`string`?e.card_id:``}}function Z(e,t){return`${e}\u0000${t}`}function je(e,t){if(t.size===0)return[...e];let n=[];for(let r of e){let e=r.manual_labels.filter(e=>!t.has(Z(r.uid,e.id)));if(e.length===r.manual_labels.length)n.push(r);else if(r.info_type!==null||e.length>0){let t=e.length===0&&r.override?.mode===`disable`;n.push({...r,manual_labels:e,...t?{disabled:!0,completed:!0,is_test:!1}:{}})}}return n}function Me(e,t,n){let r=Y(t,Math.max(n,21));for(let t of e)t.date>r&&(r=t.date);return{min:t,max:r}}function Ne(e){return/T(\d{2}:\d{2})/.exec(e)?.[1]??``}function Pe(e){if(e.all_day)return``;let t=Ne(e.start),n=Ne(e.end);return t&&n?`${t}\u2013${n}`:t}function Fe(e){let t=2166136261;for(let n=0;n<e.length;n++)t^=e.charCodeAt(n),t=Math.imul(t,16777619)>>>0;return t.toString(16).padStart(8,`0`)}function Ie(){try{return[...crypto.getRandomValues(/* @__PURE__ */ new Uint8Array(6))].map(e=>e.toString(16).padStart(2,`0`)).join(``)}catch{return Math.random().toString(36).slice(2,14).padEnd(12,`0`)}}function Le(e){let t=e.card_id||Fe(`${e.entity}\u0000${e.title}`),n=Fe(JSON.stringify([e.entity,e.title,e.card_id,e.language,e.show_completed,e.show_past,e.days_ahead,e.show_progress_tomorrow,e.show_progress_week,e.show_progress_next_week]));return`magister-homework-card:${e.entity}:${t}:${n}`}function Re(e){try{let t=window.localStorage.getItem(e);if(t===null)return;let n=JSON.parse(t);if(typeof n?.show_completed==`boolean`&&typeof n.show_past==`boolean`)return{show_completed:n.show_completed,show_past:n.show_past}}catch{}}function ze(e,t){try{window.localStorage.setItem(e,JSON.stringify(t))}catch{return}try{let t=e.slice(0,e.lastIndexOf(`:`)+1),n=[];for(let r=0;r<window.localStorage.length;r++){let i=window.localStorage.key(r);i!==null&&i!==e&&i.startsWith(t)&&n.push(i)}for(let e of n)window.localStorage.removeItem(e)}catch{}}var Be={1:`default_homework`,2:`default_test`,3:`default_exam`,4:`default_written_quiz`,5:`default_oral_quiz`};function Ve(e,t){let n=e.manual_labels.some(e=>e.kind===`test`);switch(t.mode){case`replace`:return{override:{mode:`replace`,label:t.label},disabled:!1,is_test:t.label.kind===`test`||n};case`disable`:return{override:{mode:`disable`},disabled:e.manual_labels.length===0,is_test:n};case`clear`:return{override:null,disabled:!1,is_test:e.info_type!==null&&e.info_type>=2||n}}}function He(e){return{override:e.override??null,disabled:e.disabled===!0,is_test:e.is_test}}function Ue(e,t){return!e||!t?!e&&!t:e.mode===t.mode?e.mode===`replace`&&t.mode===`replace`?e.label.id===t.label.id:!0:!1}function We(e,t){return Ue(e.override,t.override)&&e.disabled===!0==(t.disabled===!0)&&e.is_test===t.is_test}function Ge(e,t){return t.size===0?[...e]:e.map(e=>{let n=t.get(e.uid);return n?{...e,...n,completed:e.progress>=100||n.disabled===!0}:e})}function Ke(e,t){let n=e.info_type===null?void 0:Be[e.info_type],r=e.override?.mode===`replace`?e.override.label.id:void 0;return{replace:e.disabled===!0?[]:t.filter(e=>e.id!==n&&e.id!==r),disable:e.disabled!==!0&&e.override?.mode!==`disable`,restore:e.override!=null}}var qe={nl:{today:`Vandaag`,tomorrow:`Morgen`,earlier:`Eerder`,no_homework:`Geen huiswerk 🎉`,loading:`Laden…`,unavailable:`Magister is niet beschikbaar. Je ziet het laatst bekende huiswerk; wijzigen kan nu niet.`,offline:`Verbinding met Home Assistant verbroken. Opnieuw verbinden…`,choose_entity:`Kies een Magister-huiswerklijst in de kaartinstellingen.`,not_found:`Deze huiswerklijst is niet gevonden.`,unauthorized:`Je hebt geen toegang tot deze huiswerklijst.`,load_failed:`Het huiswerk kon niet worden geladen.`,save_failed:`Opslaan mislukt. De wijziging is teruggedraaid.`,save_unauthorized:`Geen rechten om voortgang te wijzigen.`,dismiss:`Sluiten`,cancelled:`Les vervallen`,attachments:`Bijlagen in Magister`,lesson_hour:`Uur {n}`,mark_done:`Markeer {subject} als klaar`,mark_open:`Markeer {subject} als niet klaar`,progress_of:`Voortgang van {subject}`,percent:`{n} %`,expand:`Toon de volledige tekst`,collapse:`Toon minder`,progress_label:{next_day:`Volgende schooldag`,week:`Deze week`,next_week:`Volgende week`},progress_done:`{completed} van {items} klaar`,progress_empty:`geen huiswerk`,progress_unavailable:`niet beschikbaar`,switches_label:`Weergave`,show_completed_switch:`Afgerond`,show_completed_tip:`Toon afgerond huiswerk`,show_past_switch:`Eerder`,show_past_tip:`Toon eerdere dagen`,add_label:`Label toevoegen`,remove_label:`Label {name} verwijderen`,confirm_remove:`Label {name} verwijderen?`,confirm_yes:`Verwijderen`,confirm_no:`Annuleren`,override_menu:`Magister-label van {subject} wijzigen`,override_tip:`Magister-label wijzigen`,override_replace_with:`Vervangen door…`,override_replace_option:`Vervangen door {name}`,override_disable:`Uitschakelen`,override_restore:`Herstellen`,override_replaced:`vervangen`,override_disabled:`uitgeschakeld`,kind:{homework:`huiswerk`,test:`toets`},all_day:`Hele dag`,dialog:{title:`Label toevoegen`,date:`Dag`,lessons:`Les`,lessons_loading:`Lessen laden…`,no_lessons:`Geen lessen op deze dag.`,label:`Label`,choose_label:`Kies een label`,note:`Notitie (optioneel)`,note_count:`{n} van 200 tekens`,save:`Opslaan`,saving:`Opslaan…`,cancel:`Annuleren`,close:`Sluiten`},label_errors:{unauthorized:`Je hebt geen rechten om labels te wijzigen.`,not_found:`Deze huiswerklijst is niet gevonden.`,invalid_format:`Ongeldige invoer.`,invalid_date:`Deze dag valt buiten de opgehaalde periode.`,appointment_not_found:`Deze les is niet meer gevonden. Kies de dag opnieuw.`,label_not_found:`Dit label bestaat niet meer. Kies een ander label.`,label_exists:`Deze les heeft dit label al.`,label_not_on_appointment:`Dit label staat niet meer op de les.`,no_magister_label:`Deze les heeft geen Magister-label om te wijzigen.`,item_disabled:`Dit item is uitgeschakeld. Herstel eerst het Magister-label.`,default:`Opslaan mislukt.`,load_default:`De lessen konden niet worden geladen.`},type:{1:`Huiswerk`,2:`Proefwerk`,3:`Tentamen`,4:`SO`,5:`MO`},editor:{entity:`Huiswerklijst (to-do van een kind)`,title:`Titel (optioneel)`,language:`Taal van de kaart`,language_auto:`Automatisch (taal van Home Assistant)`,show_completed:`Toon afgerond huiswerk`,show_past:`Toon eerdere dagen`,days_ahead:`Dagen vooruit`,show_progress_tomorrow:`Toon voortgang volgende schooldag`,show_progress_week:`Toon voortgang van deze week`,show_progress_next_week:`Toon voortgang van volgende week`}},en:{today:`Today`,tomorrow:`Tomorrow`,earlier:`Earlier`,no_homework:`No homework`,loading:`Loading…`,unavailable:`Magister is not available. You see the last known homework; changes are not possible now.`,offline:`Connection to Home Assistant lost. Reconnecting…`,choose_entity:`Choose a Magister homework list in the card settings.`,not_found:`This homework list was not found.`,unauthorized:`You have no access to this homework list.`,load_failed:`The homework could not be loaded.`,save_failed:`Saving failed. The change was rolled back.`,save_unauthorized:`No permission to change progress.`,dismiss:`Dismiss`,cancelled:`Lesson cancelled`,attachments:`Attachments in Magister`,lesson_hour:`Period {n}`,mark_done:`Mark {subject} as done`,mark_open:`Mark {subject} as not done`,progress_of:`Progress of {subject}`,percent:`{n}%`,expand:`Show the full text`,collapse:`Show less`,progress_label:{next_day:`Next school day`,week:`This week`,next_week:`Next week`},progress_done:`{completed} of {items} done`,progress_empty:`no homework`,progress_unavailable:`not available`,switches_label:`View`,show_completed_switch:`Done`,show_completed_tip:`Show completed homework`,show_past_switch:`Earlier`,show_past_tip:`Show earlier days`,add_label:`Add label`,remove_label:`Remove label {name}`,confirm_remove:`Remove label {name}?`,confirm_yes:`Remove`,confirm_no:`Cancel`,override_menu:`Change the Magister label of {subject}`,override_tip:`Change the Magister label`,override_replace_with:`Replace with…`,override_replace_option:`Replace with {name}`,override_disable:`Disable`,override_restore:`Restore`,override_replaced:`replaced`,override_disabled:`disabled`,kind:{homework:`homework`,test:`test`},all_day:`All day`,dialog:{title:`Add label`,date:`Day`,lessons:`Lesson`,lessons_loading:`Loading lessons…`,no_lessons:`No lessons on this day.`,label:`Label`,choose_label:`Choose a label`,note:`Note (optional)`,note_count:`{n} of 200 characters`,save:`Save`,saving:`Saving…`,cancel:`Cancel`,close:`Close`},label_errors:{unauthorized:`You have no permission to change labels.`,not_found:`This homework list was not found.`,invalid_format:`Invalid input.`,invalid_date:`This day is outside the fetched period.`,appointment_not_found:`This lesson was not found any more. Choose the day again.`,label_not_found:`This label no longer exists. Choose another label.`,label_exists:`This lesson already has this label.`,label_not_on_appointment:`This label is no longer on the lesson.`,no_magister_label:`This lesson has no Magister label to change.`,item_disabled:`This item is disabled. Restore the Magister label first.`,default:`Saving failed.`,load_default:`The lessons could not be loaded.`},type:{1:`Homework`,2:`Test`,3:`Exam`,4:`Short test`,5:`Oral test`},editor:{entity:`Homework list (a child's to-do)`,title:`Title (optional)`,language:`Card language`,language_auto:`Automatic (Home Assistant language)`,show_completed:`Show completed homework`,show_past:`Show earlier days`,days_ahead:`Days ahead`,show_progress_tomorrow:`Show next school day progress`,show_progress_week:`Show progress for this week`,show_progress_next_week:`Show progress for next week`}}};function Je(e,t){return e===`nl`||e===`en`?e:Ye(t)}function Ye(e){return e?.toLowerCase().startsWith(`nl`)?`nl`:`en`}function Xe(e){return qe[Ye(e)]}function Q(e,t){return e.replace(/\{(\w+)\}/g,(e,n)=>n in t?String(t[n]):e)}function Ze(e,t,n){return e.type[t]??n}function Qe(e=Xe(`en`)){return[{name:`entity`,required:!0,selector:{entity:{filter:{domain:`todo`,integration:`magister`}}}},{name:`title`,selector:{text:{}}},{name:`language`,selector:{select:{mode:`dropdown`,options:[{value:`auto`,label:e.editor.language_auto},{value:`nl`,label:`Nederlands`},{value:`en`,label:`English`}]}}},{name:`show_completed`,selector:{boolean:{}}},{name:`show_past`,selector:{boolean:{}}},{name:`days_ahead`,selector:{number:{min:0,max:365,step:1,mode:`box`}}},...X.map(({option:e})=>({name:e,selector:{boolean:{}}}))]}function $e(e){return{entity:e.entity??``,title:e.title??``,language:e.language??`auto`,show_completed:e.show_completed??!1,show_past:e.show_past??!1,days_ahead:e.days_ahead??7,show_progress_tomorrow:e.show_progress_tomorrow??!1,show_progress_week:e.show_progress_week??!1,show_progress_next_week:e.show_progress_next_week??!1}}function et(e,t){let n={...e,type:e.type??`custom:magister-homework-card`,entity:typeof t.entity==`string`?t.entity:e.entity??``},r=t.title;typeof r==`string`&&r.trim()!==``?n.title=r:delete n.title;let i=t.language;i===`nl`||i===`en`?n.language=i:delete n.language,t.show_completed===!0?n.show_completed=!0:delete n.show_completed,t.show_past===!0?n.show_past=!0:delete n.show_past;let a=n;for(let{option:e}of X)t[e]===!0?a[e]=!0:delete a[e];let o=t.days_ahead,s=o===``||o==null?NaN:Number(o);return Number.isFinite(s)&&s>=0&&s!==7?n.days_ahead=Math.min(Math.floor(s),365):delete n.days_ahead,n}var tt=class extends W{constructor(...e){super(...e),this._computeLabel=e=>this._texts().editor[e.name]??e.name,this._valueChanged=e=>{if(e.stopPropagation(),!this._config)return;let t=et(this._config,e.detail.value);t.card_id??=Ie(),this._config=t,this.dispatchEvent(new CustomEvent(`config-changed`,{detail:{config:t},bubbles:!0,composed:!0}))}}static{this.properties={hass:{attribute:!1},_config:{state:!0}}}setConfig(e){this._config=e}_texts(){return Xe(this.hass?.locale?.language??this.hass?.language)}render(){return this._config?N`<ha-form
      .hass=${this.hass}
      .data=${$e(this._config)}
      .schema=${Qe(this._texts())}
      .computeLabel=${this._computeLabel}
      @value-changed=${this._valueChanged}
    ></ha-form>`:F}},nt=`magister/homework/appointments`,rt=`magister/homework/add_label`,it=class extends W{static{this.properties={hass:{attribute:!1},entity:{attribute:!1},labels:{attribute:!1},texts:{attribute:!1},language:{attribute:!1},today:{attribute:!1},min:{attribute:!1},max:{attribute:!1},_date:{state:!0},_appointments:{state:!0},_loading:{state:!0},_loadError:{state:!0},_selected:{state:!0},_label:{state:!0},_note:{state:!0},_saving:{state:!0},_error:{state:!0}}}constructor(){super(),this._request=0,this._closedSent=!1,this._date=``,this._appointments=[],this._loading=!1,this._loadError=``,this._selected=``,this._label=``,this._note=``,this._saving=!1,this._error=``}connectedCallback(){super.connectedCallback(),this._date=this.today}firstUpdated(){let e=this._dialog();e&&(typeof e.showModal==`function`?e.showModal():e.setAttribute(`open`,``)),this._load(this._date)}disconnectedCallback(){super.disconnectedCallback(),this._request++}_dialog(){return this.renderRoot.querySelector(`dialog`)}_close(){let e=this._dialog();e?.open&&e.close(),this._emitClosed()}_emitClosed(){this._closedSent||(this._closedSent=!0,this.dispatchEvent(new CustomEvent(`dialog-closed`,{bubbles:!0,composed:!0})))}async _load(e){let t=this.hass,n=++this._request;if(this._appointments=[],this._selected=``,this._loadError=``,this._error=``,!t||!e)this._loading=!1;else{this._loading=!0;try{let r=await t.callWS({type:nt,entity_id:this.entity,date:e});if(n!==this._request)return;this._appointments=r.appointments}catch(e){if(n!==this._request)return;this._loadError=this._message(e,this.texts.label_errors.load_default??``)}finally{n===this._request&&(this._loading=!1)}}}_message(e,t){let n=e?.code;return(n?this.texts.label_errors[n]:void 0)??t}async _save(){let e=this.hass;if(!e||this._saving||!this._selected||!this._label)return;let t={type:rt,entity_id:this.entity,appointment:this._selected,label:this._label},n=this._note.trim();n&&(t.note=n),this._saving=!0,this._error=``;try{await e.callWS(t),this._saving=!1,this.dispatchEvent(new CustomEvent(`label-added`,{bubbles:!0,composed:!0})),this._close()}catch(e){this._saving=!1,this._error=this._message(e,this.texts.label_errors.default??``)}}_describe(e){let t=this.texts,n=[];e.info_type!==null&&n.push(Ze(t,e.info_type,``));for(let t of e.manual_labels)n.push(t.name);return n.filter(Boolean).join(`, `)}render(){let e=this.texts,t=e.dialog,n=!this._saving&&this._selected!==``&&this._label!==``;return N`<dialog
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
          ${this._date?N`<small>${Ce(this._date,this.language===`nl`?`nl`:`en-GB`)}</small>`:F}
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
            ${this.labels.map(t=>N`<option value=${t.id} ?selected=${this._label===t.id}>
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
          <small class="count">${Q(t.note_count,{n:this._note.length})}</small>
        </label>

        ${this._error?N`<p class="error" role="alert">${this._error}</p>`:F}

        <footer>
          <button type="button" class="secondary" @click=${()=>{this._close()}}>${t.cancel}</button>
          <button type="submit" class="primary" ?disabled=${!n}>
            ${this._saving?t.saving:t.save}
          </button>
        </footer>
      </form>
    </dialog>`}_renderLessons(){let e=this.texts;return this._loading?N`<p class="hint" role="status">${e.dialog.lessons_loading}</p>`:this._loadError?N`<p class="error" role="alert">${this._loadError}</p>`:this._appointments.length===0?N`<p class="hint" role="status">${e.dialog.no_lessons}</p>`:N`${this._appointments.map(t=>{let n=t.all_day?e.all_day:Pe(t),r=this._describe(t);return N`<label class="lesson ${t.cancelled?`cancelled`:``}">
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
            ${t.lesson_hour===null?F:N`<span class="meta">${Q(e.lesson_hour,{n:t.lesson_hour})}</span>`}
            ${n?N`<span class="meta">${n}</span>`:F}
            ${t.cancelled?N`<span class="badge">${e.cancelled}</span>`:F}
          </span>
          ${r?N`<span class="lesson-labels">${r}</span>`:F}
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
  `}},at=`magister/homework/subscribe`,ot=`magister/homework/set_progress`,st=`magister/homework/remove_label`,ct=`magister/homework/set_override`,lt=6e3,$=3e4,ut=6e5,dt=`M16.5,6V17.5A4,4 0 0,1 12.5,21.5A4,4 0 0,1 8.5,17.5V5A2.5,2.5 0 0,1 11,2.5A2.5,2.5 0 0,1 13.5,5V15.5A1,1 0 0,1 12.5,16.5A1,1 0 0,1 11.5,15.5V6H10V15.5A2.5,2.5 0 0,0 12.5,18A2.5,2.5 0 0,0 15,15.5V5A4,4 0 0,0 11,1A4,4 0 0,0 7,5V17.5A5.5,5.5 0 0,0 12.5,23A5.5,5.5 0 0,0 18,17.5V6H16.5Z`;function ft(e){try{Promise.resolve(e()).catch(()=>void 0)}catch{}}var pt=class extends W{static{this.properties={_payload:{state:!0},_loadError:{state:!0},_offline:{state:!0},_overlay:{state:!0},_expanded:{state:!0},_toast:{state:!0},_showCompleted:{state:!0},_showPast:{state:!0},_hiddenLabels:{state:!0},_confirm:{state:!0},_dialogOpen:{state:!0},_overrideOverlay:{state:!0},_menu:{state:!0}}}constructor(){super(),this._storageKey=``,this._removing=/* @__PURE__ */ new Set,this._subscribedEntity=``,this._generation=0,this._tokens=/* @__PURE__ */ new Map,this._overrideTokens=/* @__PURE__ */ new Map,this._nextToken=0,this._retryDelay=$,this._hassKey=``,this._shownDay=``,this._touched=/* @__PURE__ */ new Set,this._onDisconnected=()=>{this._offline=!0},this._onReady=()=>{this._offline=!1,this._loadError&&this._retry()},this._onOutsideClick=e=>{let t=this._menu;if(t===void 0)return;let n=e.composedPath(),r=this.shadowRoot?.querySelector(`.menu`);r&&n.includes(r)||n.includes(this._menuButton(t))||this._closeMenu(!1)},this._closeDialog=()=>{this._dialogOpen=!1,this.updateComplete.then(()=>{this.shadowRoot?.querySelector(`.add`)?.focus()})},this._offline=!1,this._overlay=/* @__PURE__ */ new Map,this._expanded=/* @__PURE__ */ new Set,this._toast=``,this._showCompleted=!1,this._showPast=!1,this._hiddenLabels=/* @__PURE__ */ new Set,this._confirm=void 0,this._dialogOpen=!1,this._overrideOverlay=/* @__PURE__ */ new Map,this._menu=void 0}static getConfigElement(){return document.createElement(`magister-homework-card-editor`)}static getStubConfig(e){return{entity:Object.entries(e?.entities??{}).find(([e,t])=>e.startsWith(`todo.`)&&t?.platform===`magister`)?.[0]??``}}setConfig(e){let t=Ae(e);t.entity!==this._config?.entity&&(this._resetSubscription(),this._payload=void 0,this._loadError=void 0,this._offline=!1,this._overlay=/* @__PURE__ */ new Map,this._expanded=/* @__PURE__ */ new Set,this._tokens.clear(),this._touched.clear(),this._hiddenLabels=/* @__PURE__ */ new Set,this._removing.clear(),this._confirm=void 0,this._dialogOpen=!1,this._overrideOverlay=/* @__PURE__ */ new Map,this._overrideTokens.clear(),this._closeMenu(!1),this._retryDelay=$),this._config=t,this._storageKey=Le(t);let n=Re(this._storageKey);this._showCompleted=n?.show_completed??t.show_completed,this._showPast=n?.show_past??t.show_past,this.requestUpdate(),this._ensureSubscription()}set hass(e){this._hass=e;let t=`${e?.locale?.language??``}|${e?.language??``}|${e?.config?.time_zone??``}`;t===this._hassKey&&this._payload||(this._hassKey=t,this.requestUpdate()),this._ensureSubscription()}get hass(){return this._hass}getCardSize(){let e=this._visibleItems().length;return e===0?3:2+e*2}getGridOptions(){return{columns:12,min_columns:6,min_rows:3}}connectedCallback(){super.connectedCallback(),this._ensureSubscription(),this._dayTimer=setInterval(()=>{this._currentDay()!==this._shownDay&&this.requestUpdate()},6e4)}disconnectedCallback(){super.disconnectedCallback(),this._resetSubscription(),this._toastTimer&&clearTimeout(this._toastTimer),this._dayTimer&&clearInterval(this._dayTimer),this._dayTimer=void 0,this._closeMenu(!1)}_ensureSubscription(){let e=this._hass,t=this._config?.entity;if(!this.isConnected||!e?.connection||!t||this._subscribedEntity===t&&this._connection===e.connection)return;this._resetSubscription(),this._attach(e.connection),this._subscribedEntity=t;let n=++this._generation;e.connection.subscribeMessage(e=>{n===this._generation&&this._onPayload(e)},{type:at,entity_id:t},{resubscribe:!0}).then(e=>{n===this._generation?this._unsubscribe=e:ft(e)},e=>{if(n!==this._generation)return;let t=e?.code;this._loadError=t===`not_found`||t===`invalid_format`?`not_found`:t===`unauthorized`?`unauthorized`:`load_failed`,this._scheduleRetry()})}_scheduleRetry(){this._retryTimer&&clearTimeout(this._retryTimer),this._retryTimer=setTimeout(()=>{this._retryTimer=void 0,this._retry()},this._retryDelay),this._retryDelay=Math.min(this._retryDelay*2,ut)}_retry(){this._resetSubscription(),this._ensureSubscription()}_attach(e){e.addEventListener?.(`disconnected`,this._onDisconnected),e.addEventListener?.(`ready`,this._onReady),this._connection=e,e.connected===!1&&(this._offline=!0)}_resetSubscription(){this._generation++,this._unsubscribe&&ft(this._unsubscribe),this._unsubscribe=void 0,this._retryTimer&&clearTimeout(this._retryTimer),this._retryTimer=void 0,this._connection?.removeEventListener?.(`disconnected`,this._onDisconnected),this._connection?.removeEventListener?.(`ready`,this._onReady),this._connection=void 0,this._subscribedEntity=``}_onPayload(e){this._payload=e,this._loadError=void 0,this._retryDelay=$,this._offline=!1;let t=/* @__PURE__ */ new Map;for(let[e,n]of this._overlay)this._tokens.has(e)&&t.set(e,n);this._overlay=t;let n=/* @__PURE__ */ new Map;for(let[e,t]of this._overrideOverlay)this._overrideTokens.has(e)&&n.set(e,t);this._overrideOverlay=n,this._hiddenLabels=new Set([...this._hiddenLabels].filter(e=>this._removing.has(e)))}async _setProgress(e,t){let n=this._hass,r=this._config?.entity,i=this._payload?.items.find(t=>t.uid===e);if(!n||!r||!i||!this._payload?.available||this._offline)return;let a=++this._nextToken;this._tokens.set(e,a),t>=100&&this._touched.add(e);let o=De(Oe([i],this._overlay)[0]??i,t);this._overlay=new Map(this._overlay).set(e,o);try{let i=await n.callWS({type:ot,entity_id:r,item:e,progress:t});if(this._tokens.get(e)!==a)return;this._tokens.delete(e);let s=this._payload.items.find(t=>t.uid===e),c=new Map(this._overlay);s?.progress===i.progress?c.delete(e):c.set(e,{...o,progress:i.progress,completed:i.completed}),this._overlay=c}catch(t){if(this._tokens.get(e)!==a)return;this._tokens.delete(e);let n=new Map(this._overlay);n.delete(e),this._overlay=n;let r=t?.code,i=this._texts();this._showToast(r===`unauthorized`?i.save_unauthorized:r===`item_disabled`?i.label_errors.item_disabled??i.save_failed:i.save_failed)}}_showToast(e){this._toast=e,this._toastTimer&&clearTimeout(this._toastTimer),this._toastTimer=setTimeout(()=>{this._toast=``},lt)}_toggleExpanded(e){let t=new Set(this._expanded);t.delete(e)||t.add(e),this._expanded=t}_menuButton(e){return this.shadowRoot?.querySelector(`[data-menu-button="${CSS.escape(e)}"]`)??null}_menuItems(){return[...this.shadowRoot?.querySelectorAll(`.menu [role="menuitem"]`)??[]]}_openMenu(e,t){this._menu=e,document.addEventListener(`click`,this._onOutsideClick,!0),this.updateComplete.then(()=>{let e=this._menuItems();(t===`first`?e[0]:e[e.length-1])?.focus()})}_closeMenu(e){let t=this._menu;document.removeEventListener(`click`,this._onOutsideClick,!0),t!==void 0&&(this._menu=void 0,e&&this.updateComplete.then(()=>{this._menuButton(t)?.focus()}))}_onChipKey(e,t){e.key===`ArrowDown`?(e.preventDefault(),this._openMenu(t,`first`)):e.key===`ArrowUp`?(e.preventDefault(),this._openMenu(t,`last`)):e.key===`Escape`&&this._menu===t&&(e.preventDefault(),this._closeMenu(!0))}_onMenuKey(e,t){let n=this._menuItems(),r=n.indexOf(e.target),i;switch(e.key){case`ArrowDown`:i=(r+1)%n.length;break;case`ArrowUp`:i=(r-1+n.length)%n.length;break;case`Home`:i=0;break;case`End`:i=n.length-1;break;case`Escape`:e.preventDefault(),e.stopPropagation(),this._closeMenu(!0);return;case`Tab`:this._menuButton(t)?.focus(),this._closeMenu(!1);return;default:return}e.preventDefault(),n[i]?.focus()}_choose(e,t){this._closeMenu(!0),this._setOverride(e,t)}async _setOverride(e,t){let n=this._hass,r=this._config?.entity,i=e.uid;if(!n||!r||!this._payload?.available||this._offline)return;let a=++this._nextToken;this._overrideTokens.set(i,a),t.mode===`disable`&&this._touched.add(i);let o=this._items().find(e=>e.uid===i)??e;this._overrideOverlay=new Map(this._overrideOverlay).set(i,Ve(o,t));try{let e=await n.callWS({type:ct,entity_id:r,appointment:i,mode:t.mode,...t.mode===`replace`?{label:t.label.id}:{}});if(this._overrideTokens.get(i)!==a)return;this._overrideTokens.delete(i);let o=new Map(this._overrideOverlay),s=this._payload.items.find(e=>e.uid===i),c=e.item?He(e.item):void 0;!c||s&&We(s,c)?o.delete(i):o.set(i,c),this._overrideOverlay=o}catch(e){if(this._overrideTokens.get(i)!==a)return;this._overrideTokens.delete(i);let t=new Map(this._overrideOverlay);t.delete(i),this._overrideOverlay=t;let n=e?.code,r=this._texts();this._showToast((n?r.label_errors[n]:void 0)??r.save_failed)}}_askRemove(e,t){this._confirm={uid:e,label:t},this.updateComplete.then(()=>{this.shadowRoot?.querySelector(`.confirm .cancel`)?.focus()})}_cancelRemove(){let e=this._confirm;this._confirm=void 0,e&&this.updateComplete.then(()=>{this.shadowRoot?.querySelector(`[data-key="${CSS.escape(Z(e.uid,e.label.id))}"]`)?.focus()})}async _removeLabel(e,t){let n=this._hass,r=this._config?.entity;if(this._confirm=void 0,!n||!r)return;let i=Z(e,t.id);this._removing.add(i),this._hiddenLabels=new Set(this._hiddenLabels).add(i),this.updateComplete.then(()=>{let t=this.shadowRoot?.querySelector(`li[data-uid="${CSS.escape(e)}"]`);(t?.querySelector(`.chip-remove:not(:disabled)`)??t?.querySelector(`input[type="checkbox"]`)??this.shadowRoot?.querySelector(`.add`))?.focus()});try{await n.callWS({type:st,entity_id:r,appointment:e,label:t.id}),this._removing.delete(i)}catch(e){this._removing.delete(i);let t=e?.code;if(t===`label_not_on_appointment`)return;let n=new Set(this._hiddenLabels);n.delete(i),this._hiddenLabels=n;let r=this._texts();this._showToast((t?r.label_errors[t]:void 0)??r.save_failed)}}_language(){return Je(this._config?.language,this._hass?.locale?.language??this._hass?.language)}_texts(){return qe[this._language()]}_items(){return this._payload?je(Ge(Oe(this._payload.items,this._overlay),this._overrideOverlay),this._hiddenLabels):[]}_setSwitch(e,t){e===`show_completed`?this._showCompleted=t:this._showPast=t,ze(this._storageKey,{show_completed:this._showCompleted,show_past:this._showPast})}_currentDay(){return Se(/* @__PURE__ */ new Date,this._hass?.config?.time_zone)}_today(){return this._shownDay=this._currentDay(),this._shownDay}_visibleItems(){let e=this._config;return!e||!this._payload?[]:we(this._items(),{showCompleted:this._showCompleted,showPast:this._showPast,daysAhead:e.days_ahead,today:this._today(),keep:this._touched})}_dayTitle(e,t){return e.kind===`today`?t.today:e.kind===`tomorrow`?t.tomorrow:Ce(e.date,this._language()===`nl`?`nl`:`en-GB`)}willUpdate(){this._confirm&&(this._offline||this._payload?.available!==!0)&&(this._confirm=void 0),this._menu!==void 0&&(this._offline||this._payload?.available!==!0||!this._payload.items.some(e=>e.uid===this._menu))&&this._closeMenu(!1)}render(){let e=this._config,t=this._texts();return N`<ha-card .header=${e?.title??``}>
      <div class="content ${e?.title?`titled`:``}">${this._renderBody(t)}</div>
      ${this._toast?N`<div class="toast" role="alert">
            <span>${this._toast}</span>
            <button type="button" @click=${()=>{this._toast=``}}>${t.dismiss}</button>
          </div>`:F}
      ${this._renderDialog(t)}
    </ha-card>`}_renderBody(e){if(!this._config?.entity)return N`<p class="state">${e.choose_entity}</p>`;if(this._loadError)return N`<p class="state error">${e[this._loadError]}</p>`;if(!this._payload)return N`<p class="state">${e.loading}</p>`;let t=this._payload.available,n=t&&!this._offline,r=Ee(this._visibleItems(),this._today()),i=this._renderBars(e,this._offline),a=N`${this._renderToolbar(e,n)}${i}${t?F:N`<p class="banner" role="status">${e.unavailable}</p>`}${this._offline?N`<p class="banner" role="status">${e.offline}</p>`:F}`;if(r.length===0)return t?N`${a}<p class="state empty">${e.no_homework}</p>`:N`${a}`;let o=r.findIndex(e=>e.kind===`past`);return N`${a}<div class="days ${t?``:`stale`}">
        ${r.map((t,r)=>N`
            ${r===o?N`<h3 class="section">${e.earlier}</h3>`:F}
            <section class="day" aria-labelledby="day-${t.date}">
              <h4 id="day-${t.date}" class=${t.kind}>${this._dayTitle(t,e)}</h4>
              <ul>
                ${t.items.map(t=>this._renderItem(t,e,n))}
              </ul>
            </section>
          `)}
      </div>`}_renderToolbar(e,t){let n=this._payload?.labels??[],r=t&&n.length>0,i=(e,t,n,r)=>N`<button
      type="button"
      class="switch ${t?`on`:``}"
      aria-pressed=${t?`true`:`false`}
      title=${r}
      aria-label=${r}
      @click=${()=>{this._setSwitch(e,!t)}}
    ><span aria-hidden="true" class="tick">${t?`✓`:``}</span>${n}</button>`;return N`<div class="toolbar" role="toolbar" aria-label=${e.switches_label}>
      ${i(`show_completed`,this._showCompleted,e.show_completed_switch,e.show_completed_tip)}
      ${i(`show_past`,this._showPast,e.show_past_switch,e.show_past_tip)}
      ${r?N`<button
            type="button"
            class="add"
            title=${e.add_label}
            aria-label=${e.add_label}
            aria-haspopup="dialog"
            @click=${()=>{this._dialogOpen=!0}}
          >+</button>`:F}
    </div>`}_renderDialog(e){let t=this._payload,n=this._config;if(!this._dialogOpen||!t||!n)return F;let r=this._currentDay(),i=Me(t.items,r,n.days_ahead);return N`<magister-label-dialog
      .hass=${this._hass}
      .entity=${n.entity}
      .labels=${t.labels??[]}
      .texts=${e}
      .language=${this._language()}
      .today=${r}
      .min=${i.min}
      .max=${i.max}
      @dialog-closed=${this._closeDialog}
    ></magister-label-dialog>`}_renderBars(e,t){let n=this._config,r=this._payload?.progress,i=X.filter(({option:e})=>n?.[e]);return i.length===0?F:N`<div class="bars ${t?`stale`:``}">
      ${i.map(({period:t})=>{let n=e.progress_label[t],i=r?.[t]??null;if(!i)return N`<div class="bar unavailable">
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
          </div>`;let a=ke(i),o=Q(e.percent,{n:a}),s=i.items===0?e.progress_empty:Q(e.progress_done,{completed:i.completed,items:i.items});return N`<div class="bar">
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
    </div>`}_renderItem(e,t,n){let r=this._expanded.has(e.uid),i=e.manual_labels.filter(e=>e.note!==``),a=this._confirm?.uid===e.uid?this._confirm.label:void 0,o=e.uid;return N`<li class=${[`item`,e.is_test?`test`:``,e.completed?`done`:``,e.disabled===!0?`disabled`:``,e.cancelled?`cancelled`:``].filter(Boolean).join(` `)} data-uid=${o}>
      <input
        type="checkbox"
        .checked=${e.completed}
        ?disabled=${!n||e.disabled===!0}
        aria-label=${Q(e.completed?t.mark_open:t.mark_done,{subject:e.subject})}
        @change=${()=>void this._setProgress(e.uid,xe(e))}
      />
      <div class="main">
        <div class="head">
          ${this._renderMagisterChip(e,t,n)}
          ${e.manual_labels.map(r=>this._renderManualChip(e.uid,r,t,n))}
          <span class="subject">${e.subject}</span>
          ${e.lesson_hour===null?F:N`<span class="meta">${Q(t.lesson_hour,{n:e.lesson_hour})}</span>`}
          ${e.cancelled?N`<span class="badge">${t.cancelled}</span>`:F}
          ${e.has_attachments?N`<span class="meta attachments" title=${t.attachments}
                ><svg viewBox="0 0 24 24" aria-hidden="true"><path d=${dt}></path></svg
                ><span class="sr-only">${t.attachments}</span></span
              >`:F}
        </div>
        ${this._menu===e.uid?this._renderMenu(e,t):F}
        ${e.text?N`<button
              type="button"
              class="text ${r?`expanded`:``}"
              aria-expanded=${r?`true`:`false`}
              title=${r?t.collapse:t.expand}
              @click=${()=>{this._toggleExpanded(e.uid)}}
            >${e.text}</button>`:F}
        ${i.map(e=>N`<p class="note"><span class="note-label">${e.name}</span> ${e.note}</p>`)}
        ${a?N`<div
              class="confirm"
              role="group"
              aria-label=${Q(t.confirm_remove,{name:a.name})}
              @keydown=${e=>{e.key===`Escape`&&(e.stopPropagation(),this._cancelRemove())}}
            >
              <span>${Q(t.confirm_remove,{name:a.name})}</span>
              <button type="button" class="cancel" @click=${()=>{this._cancelRemove()}}>${t.confirm_no}</button>
              <button type="button" class="danger" ?disabled=${!n} @click=${()=>{this._removeLabel(e.uid,a)}}>${t.confirm_yes}</button>
            </div>`:F}
        ${this._renderProgress(e,t,n)}
      </div>
    </li>`}_renderMagisterChip(e,t,n){if(e.info_type===null)return F;let r=e.override??null,i=Ze(t,e.info_type,e.label??``),a=r?.mode===`replace`?t.override_replaced:t.override_disabled,o=`chip magister ${r?`overridden`:e.info_type>=2?`test`:``}`,s=r?N`<s>${i}</s><span class="sr-only"> ${a}</span>`:N`${i}`;return N`${n?N`<button
          type="button"
          class=${o}
          data-menu-button=${e.uid}
          aria-haspopup="menu"
          aria-expanded=${this._menu===e.uid?`true`:`false`}
          title=${t.override_tip}
          @click=${()=>{this._menu===e.uid?this._closeMenu(!0):this._openMenu(e.uid,`first`)}}
          @keydown=${t=>{this._onChipKey(t,e.uid)}}
        >${s}</button>`:N`<span class=${o}>${s}</span>`}${r?.mode===`replace`?N`<span class="chip manual plain ${r.label.kind===`test`?`test`:``}"
            >${r.label.name}</span
          >`:F}`}_renderMenu(e,t){let n=Ke(e,this._payload?.labels??[]),r=(t,n,r)=>N`<button
        type="button"
        role="menuitem"
        tabindex="-1"
        aria-label=${n}
        @click=${()=>{this._choose(e,r)}}
      >${t}</button>`;return N`<div
      class="menu"
      role="menu"
      aria-label=${Q(t.override_menu,{subject:e.subject})}
      @keydown=${t=>{this._onMenuKey(t,e.uid)}}
    >
      ${n.replace.length>0?N`<div role="group" aria-label=${t.override_replace_with}>
            <span class="menu-heading" aria-hidden="true">${t.override_replace_with}</span>
            ${n.replace.map(e=>r(e.name,Q(t.override_replace_option,{name:e.name}),{mode:`replace`,label:e}))}
          </div>`:F}
      ${n.disable?r(t.override_disable,t.override_disable,{mode:`disable`}):F}
      ${n.restore?r(t.override_restore,t.override_restore,{mode:`clear`}):F}
    </div>`}_renderManualChip(e,t,n,r){return N`<span class="chip manual ${t.kind===`test`?`test`:``}"
      >${t.name}<button
        type="button"
        class="chip-remove"
        data-key=${Z(e,t.id)}
        aria-label=${Q(n.remove_label,{name:t.name})}
        title=${Q(n.remove_label,{name:t.name})}
        ?disabled=${!r}
        @click=${()=>{this._askRemove(e,t)}}
      >×</button></span
    >`}_renderProgress(e,t,n){let r=K(e.progress),i=G.includes(e.progress);return n&&=e.disabled!==!0,N`<div class="progress">
      <div
        class="segments"
        role="radiogroup"
        aria-label=${Q(t.progress_of,{subject:e.subject})}
      >
        ${G.map(a=>N`<button
            type="button"
            role="radio"
            class="segment ${a===r?`selected`:``} ${a<r?`below`:``} ${i?``:`between`}"
            aria-checked=${i&&a===r?`true`:`false`}
            aria-label=${Q(t.percent,{n:a})}
            tabindex=${a===r?0:-1}
            ?disabled=${!n}
            @click=${()=>{a!==e.progress&&this._setProgress(e.uid,a)}}
            @keydown=${t=>{this._onSegmentKey(t,e.uid,e.progress)}}
          >
            ${a}
          </button>`)}
      </div>
      <span class="percent">${Q(t.percent,{n:e.progress})}</span>
    </div>`}_onSegmentKey(e,t,n){let r=G.indexOf(K(n)),i;switch(e.key){case`ArrowRight`:case`ArrowDown`:i=Math.min(r+1,G.length-1);break;case`ArrowLeft`:case`ArrowUp`:i=Math.max(r-1,0);break;case`Home`:i=0;break;case`End`:i=G.length-1;break;default:return}e.preventDefault();let a=G[i];if(a===void 0||a===n)return;let o=e.currentTarget;this._setProgress(t,a),this.updateComplete.then(()=>{o.parentElement?.querySelector(`[tabindex="0"]`)?.focus()})}static{this.styles=o`
    :host {
      display: block;
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
    @media (max-width: 480px) {
      .segments {
        flex: 1 1 auto;
      }
      .segment {
        min-height: 40px;
      }
    }
  `}};customElements.get(`magister-homework-card`)||customElements.define(`magister-homework-card`,pt),customElements.get(`magister-label-dialog`)||customElements.define(`magister-label-dialog`,it),customElements.get(`magister-homework-card-editor`)||customElements.define(`magister-homework-card-editor`,tt),window.customCards=window.customCards??[],window.customCards.some(e=>e.type===`magister-homework-card`)||window.customCards.push({type:`magister-homework-card`,name:`Magister Homework planner`,description:`Homework and tests of one child from Magister, with progress per item. / Huiswerk en toetsen van één kind uit Magister, met voortgang per onderdeel.`,preview:!0,documentationURL:`https://github.com/michielmj/ha_magister`});export{pt as MagisterHomeworkCard,tt as MagisterHomeworkCardEditor};