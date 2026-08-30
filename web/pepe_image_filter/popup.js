import { app, ComfyApp } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js"

import { mask_editor_listen_for_cancel, mask_editor_showing, hide_mask_editor, press_maskeditor_cancel, press_maskeditor_save, new_editor, open_maskeditor } from "./mask_utils.js";
import { Log } from "./log.js";
import { create } from "./utils.js";
import { FloatingWindow } from "./floating_window.js";
import { graph_id_to_tab } from "./graph_map.js";
import {
    DEFAULT_VIEW,
    MAX_FOV,
    MIN_FOV,
    PanoramaRenderer,
    clamp,
    degrees,
    normalizeYaw,
} from "../panorama_renderer.js";

//const EXTENSION_NODES = ["Image Filter", "Text Image Filter", "Mask Image Filter", "Text Image Filter with Extras",]
const POPUP_NODES = ["PepeImageFilter"]
const MASK_NODES = []

const REQUEST_RESHOW = "-1"
const CANCEL = "-3"

const GRID_IMAGE_SPACE = 10

function get_full_url(url) {
    return api.apiURL( `/view?filename=${encodeURIComponent(url.filename ?? v)}&type=${url.type ?? "input"}&subfolder=${url.subfolder ?? ""}&r=${Math.random()}`)
}

const State = Object.freeze({
    INACTIVE    : 0,
    TINY        : 1,
    MASK        : 2,
    FILTER      : 3,
    TEXT        : 4,
    ZOOMED      : 5,
    PROJECTED   : 6,
})

const default_audio_folder = 'extensions/ComfyUI-PepeUtils/pepe_image_filter/'
const default_audio_file = 'ding.mp3';

const stored_texts = {}

class Popup extends HTMLElement {
    constructor() {
        super()

        this.classList.add('cg_popup')

        this.grid               = create('span', 'grid', this)
        this.overlaygrid        = create('span', 'grid overlaygrid', this)
        this.grid.addEventListener('click', this.on_click.bind(this))

        this.zoomed             = create('span', 'zoomed', this)
        this.zoomed_prev        = create('span', 'zoomed_prev', this.zoomed)
        this.zoomed_prev_arrow  = create('span', 'zoomed_arrow', this.zoomed_prev, {innerHTML:"&#x21E6"})
        this.zoomed_image       = create('img',  'zoomed_image', this.zoomed)
        this.zoomed_next        = create('span', 'zoomed_next', this.zoomed)
        this.zoomed_number      = create('span', 'zoomed_number', this.zoomed_next)
        this.zoomed_next_arrow  = create('span', 'zoomed_arrow', this.zoomed_next, {innerHTML:"&#x21E8"})

        this.zoomed_prev_arrow.addEventListener('click', this.zoom_prev.bind(this))
        this.zoomed_next_arrow.addEventListener('click', this.zoom_next.bind(this))
        this.zoomed_image.addEventListener('click', this.on_zoomed_image_click.bind(this))
        this.zoomed.addEventListener('wheel', this.on_zoomed_wheel.bind(this), {passive:false})
        this.zoomed_image.addEventListener('pointerdown', this.on_zoomed_pointer_down.bind(this))
        this.zoomed_image.addEventListener('pointermove', this.on_zoomed_pointer_move.bind(this))
        this.zoomed_image.addEventListener('pointerup', this.on_zoomed_pointer_up.bind(this))
        this.zoomed_image.addEventListener('pointercancel', this.on_zoomed_pointer_up.bind(this))

        this.projected = create('span', 'projected', this)
        this.projected_toolbar = create('span', 'projected_toolbar', this.projected)
        this.projected_status = create('span', 'projected_status', this.projected_toolbar)
        this.projected_grid_button = create('button', 'control', this.projected_toolbar, {innerText:'Grid'})
        this.projected_prev_button = create('button', 'control', this.projected_toolbar, {innerText:'‹'})
        this.projected_next_button = create('button', 'control', this.projected_toolbar, {innerText:'›'})
        this.projected_reset_button = create('button', 'control', this.projected_toolbar, {innerText:'Reset'})
        this.projected_select_button = create('button', 'control', this.projected_toolbar, {innerText:'Select'})
        this.projected_fullscreen_button = create('button', 'control', this.projected_toolbar, {innerText:'⛶'})
        this.projected_canvas = create('canvas', 'projected_canvas', this.projected)
        this.projected_grid_button.addEventListener('click', this.show_grid.bind(this))
        this.projected_prev_button.addEventListener('click', ()=>this.projected_navigate(-1))
        this.projected_next_button.addEventListener('click', ()=>this.projected_navigate(1))
        this.projected_reset_button.addEventListener('click', this.reset_projected_view.bind(this))
        this.projected_select_button.addEventListener('click', this.toggle_projected_selection.bind(this))
        this.projected_fullscreen_button.addEventListener('click', this.toggle_projected_fullscreen.bind(this))
        this.projected_canvas.addEventListener('pointerdown', this.on_projected_pointer_down.bind(this))
        this.projected_canvas.addEventListener('pointermove', this.on_projected_pointer_move.bind(this))
        this.projected_canvas.addEventListener('pointerup', this.on_projected_pointer_up.bind(this))
        this.projected_canvas.addEventListener('pointercancel', this.on_projected_pointer_up.bind(this))
        this.projected_canvas.addEventListener('lostpointercapture', this.on_projected_pointer_up.bind(this))
        this.projected_canvas.addEventListener('wheel', this.on_projected_wheel.bind(this), {passive:false})
        this.projected_canvas.addEventListener('contextmenu', (e)=>e.preventDefault())
        document.addEventListener('fullscreenchange', this.on_projected_fullscreen_change.bind(this))

        this.tiny_window = new FloatingWindow('', 100, 100, null, this.tiny_moved.bind(this))
        this.tiny_window.classList.add('tiny')
        this.tiny_image         = create('img', 'tiny_image', this.tiny_window.body)
        this.tiny_window.addEventListener('click', this.handle_deferred_message.bind(this))

        this.floating_window = new FloatingWindow('', 100, 100, null, this.floater_moved.bind(this))

        this.counter_row          = create('span', 'counter row', this.floating_window.body)
        this.counter_reset_button = create('button', 'counter_reset', this.counter_row, {innerText:"Reset"} )
        this.counter_text         = create('span', 'counter_text', this.counter_row)
        this.counter_reset_button.addEventListener('click', this.request_reset.bind(this) )

        this.extras_row = create('span', 'extras row', this.floating_window.body)

        this.tip_row = create('span', 'tip row', this.floating_window.body)

        this.choices_row = create('span', 'choices row', this.floating_window.body)

        this.button_row    = create('span', 'buttons row', this.floating_window.body)
        this.send_button   = create('button', 'control', this.button_row, {innerText:"Send"} )
        this.cancel_button = create('button', 'control', this.button_row, {innerText:"Cancel"} )
        this.toggle_button = create('button', 'control', this.button_row, {innerText:"Hide"} )
        this.zoom_pan_button = create('button', 'control', this.button_row, {innerText:"Pan/Zoom"} )
        this.send_button.addEventListener(  'click', this.send_current_state.bind(this) )
        this.cancel_button.addEventListener('click', this.send_cancel.bind(this) )
        this.toggle_button.addEventListener('click', this.toggleHide.bind(this))
        this.zoom_pan_button.addEventListener('click', this.toggle_zoom_pan_mode.bind(this))

        this.mask_button_row    = create('span', 'buttons row', this.floating_window.body)
        this.mask_send_button   = create('button', 'control', this.mask_button_row, {innerText:"Send"} )
        this.mask_cancel_button = create('button', 'control', this.mask_button_row, {innerText:"Cancel"} )
        this.mask_send_button.addEventListener(  'click', press_maskeditor_save )
        this.mask_cancel_button.addEventListener('click', press_maskeditor_cancel )

        this.text_edit = create('textarea', 'text_edit row', this.floating_window.body)
        this.text_edit.id = 'text_edit'

        this.text_edit.addEventListener('click', (e)=>{
            if (e.detail==3) { this.text_edit.value = this.retrieve_text() }
        })

        this.picked = new Set()
        this.choice_names = []
        this.default_choice = 0
        this.n_choices = 0

        document.addEventListener("keydown", this.on_key_down.bind(this))
        document.addEventListener("keypress", this.on_key_press.bind(this))

        document.body.appendChild(this)
        this.last_response_sent = 0
        this.active_graph_id = null
        this.active_request_id = null
        this.state = State.INACTIVE
        this.hidden_by_toggle = false
        this.zoom_pan_mode = false
        this.projected_renderer = null
        this.projected_load_version = 0
        this.projected_view = {...DEFAULT_VIEW}
        this.projected_dragging = false
        this.reset_zoom_pan_transform()
        this.render()
    }

    unique_id() { return `${app.graph.id}:${this.node?.id}` }
    store_text(text) { stored_texts[this.unique_id()] = text }
    retrieve_text() { return stored_texts[this.unique_id()] || "" }

    toggleHide() {
        this.hidden_by_toggle = !this.hidden_by_toggle
        if (!this.hidden_by_toggle) this.layout()
        this.render()
    }

    floater_moved(x,y) {
        if (this.node?.properties) {
            this.node.properties['filter_floater_xy'] = {x:x,y:y}
        }
    }

    floater_position() {
        return this.node?.properties?.['filter_floater_xy']
    }

    tiny_moved(x,y) {
        if (this.node?.properties) {
            this.node.properties['filter_tiny_xy'] = {x:x,y:y}
        }
    }

    tiny_position() {
        return this.node?.properties?.['filter_tiny_xy']
    }

    visible(item, value) {
        if (value) item.classList.remove('hidden')
        else item.classList.add('hidden')
    }
    disabled(item, value) {
        item.disabled = value
    }
    highlighted(item, value) {
        if (value) item.classList.add('highlighted')
        else item.classList.remove('highlighted')
    }

    render() {
        const state = this.state
        if (state!=State.ZOOMED && this.zoom_pan_mode) {
            this.zoom_pan_mode = false
            this.reset_zoom_pan_transform()
        }
        this.visible(this, (state==State.FILTER || state==State.TEXT || state==State.ZOOMED || state==State.PROJECTED) && !this.hidden_by_toggle)

        this.visible(this.tiny_window, state==State.TINY)

        this.visible(this.zoomed, state==State.ZOOMED)
        this.visible(this.projected, state==State.PROJECTED)

        this.visible(this.floating_window, (state==State.FILTER || state==State.ZOOMED || state==State.PROJECTED || state==State.TEXT || state==State.MASK))
        this.visible(this.button_row, state!=State.MASK)
        this.disabled(this.send_button, (state==State.FILTER || state==State.ZOOMED || state==State.PROJECTED) && this.picked.size==0)
        this.visible(this.mask_button_row, state==State.MASK && new_editor())
        this.visible(this.extras_row, this.n_extras>0)
        this.visible(this.tip_row, this.tip_row.childNodes.length>0)
        this.visible(this.choices_row, state!=State.MASK && this.n_choices>0)
        this.visible(this.send_button, this.n_choices==0)
        this.visible(this.text_edit, state==State.TEXT)

        const choice_disabled = (state==State.FILTER || state==State.ZOOMED || state==State.PROJECTED) && this.picked.size==0
        Array.from(this.choices_row.children).forEach((button)=>{ button.disabled = choice_disabled })

        if (state==State.ZOOMED) {
            const img_index = this.zoomed_image_holder.image_index
            this.highlighted(this.zoomed, this.picked.has(`${img_index}`))
            this.zoomed_number.innerHTML = `${img_index+1}/${this.n_images}`
        }
        if (state==State.PROJECTED) this.update_projected_controls()

        if (state!=State.MASK) hide_mask_editor()

        this.toggle_button.innerText = this.hidden_by_toggle ? "Show" : "Hide"
        this.visible(this.toggle_button, (state==State.FILTER || state==State.ZOOMED || state==State.PROJECTED || state==State.TEXT))
        this.visible(this.zoom_pan_button, state==State.ZOOMED)
        this.zoom_pan_button.innerText = this.zoom_pan_mode ? "Pan/Zoom On" : "Pan/Zoom"
        if (this.zoom_pan_mode) {
            this.zoomed.classList.add('pan_zoom')
            this.zoom_pan_button.classList.add('active')
        } else {
            this.zoomed.classList.remove('pan_zoom')
            this.zoom_pan_button.classList.remove('active')
        }
    }

    _send_response(msg={}, keep_open=false) {
        /*
        msg is a dict. Valid keys are:
        *selection    (list[int])
        *text         (string)
         special      (int)
         masked_image (string)
         choice_index (int)
        *extras       (list of strings)
        *graph_id       (string)
                (*) are added
        */
        if (Date.now()-this.last_response_sent < 1000) {
            Log.message_out(msg, "(throttled)")
            return
        }

        msg.graph_id = this.active_graph_id ?? `${app.graph.id}`
        msg.request_id = this.active_request_id

        if (!msg.special) {
            if (this.n_extras>0) {
                msg.extras = []
                Array.from(this.extras_row.children).forEach((e)=>{ msg.extras.push(e.value) })
            }

            if (this.state==State.FILTER || this.state==State.ZOOMED || this.state==State.PROJECTED) {
                msg.selection = Array.from(this.picked)
            }

            if (this.state==State.TEXT) {
                msg.text = this.text_edit.value
                this.store_text(msg.text)
            }

            this.last_response_sent = Date.now()
        }

        try {
            const body = new FormData();
            body.append('response', JSON.stringify(msg));
            api.fetchApi("/pepe-image-filter-message", { method: "POST", body, });
            Log.message_out(msg)
        } catch (e) {
            Log.error(e)
        } finally {
            if (!keep_open) this.close()
        }

    }

    send_current_state() {
        if (this.n_choices>0) return this.send_choice(this.default_choice)
        this._send_response()
    }

    send_choice(choice_index) {
        if ((this.state==State.FILTER || this.state==State.ZOOMED || this.state==State.PROJECTED) && this.picked.size==0) return
        this._send_response({choice_index:choice_index})
    }

    send_cancel() { this._send_response({special:CANCEL}) }

    request_reset() { this._send_response({special:REQUEST_RESHOW}, true) }

    close() {
        if (this.state==State.MASK) {
            press_maskeditor_cancel()
        }
        this.projected_load_version += 1
        this.projected_dragging = false
        if (document.fullscreenElement===this.projected) document.exitFullscreen().catch(()=>{})
        this.exit_zoom_pan_mode()
        this.state = State.INACTIVE
        this.render()
    }

    async maybe_play_sound() {
        if (app.ui.settings.getSettingValue("Pepe Image Filter.UI.Play Sound")) {
            if (this.audiopath) {
                if (await this.play_sound(this.audiopath) ||
                    await this.play_sound(default_audio_folder + this.audiopath)) return
            }
            this.play_sound(default_audio_folder + default_audio_file)
        }
    }

    async play_sound(path) {
        if (!path) return false
        try {
            const audio = new Audio(path);
            await audio.play()
            return true
        } catch (e) {
            return false
        }
    }

    handle_message(message) {
        Log.message_in(message)
        this._handle_message(message, false)
        this.render()
    }

    handle_deferred_message(e) {
        Log.message_in(this.saved_message, "(deferred)")
        this._handle_message(this.saved_message, true)
        this.render()
    }

    autosend() {
        return (app.ui.settings.getSettingValue("Pepe Image Filter.Actions.Autosend Identical") && this.allsame)
    }

    on_new_node(nd) {
        this.node = nd
        const fp = this.floater_position()
        if (fp) this.floating_window.move_to(fp.x, fp.y, true)
        const tp = this.tiny_position()
        if (tp) this.tiny_window.move_to(tp.x, tp.y, true)
    }

    find_node(uid) {
		uid = uid.split('.').pop();

        const bits = uid.split(':')
        if (bits.length==1) {
            return app.graph._nodes_by_id[uid]
        } else {
            var graph = app.graph
            var node
            bits.forEach((bit)=>{
                node = graph._nodes_by_id[bit]
                graph = node.subgraph
            })
        }
        return node
    }

    _flash_tab(graph_id) {
        const tab = graph_id_to_tab.get(graph_id)
        if (tab) {
            const element = tab.firstElementChild?.firstElementChild?.firstElementChild || tab
            if (this.tab_orginal_background===undefined) this.tab_orginal_background = element.style.backgroundColor
            element.style.backgroundColor = '#ffff0040'
            setTimeout( ()=>{ element.style.backgroundColor = this.tab_orginal_background }, 100 )
        }
    }

    _handle_message(message, using_saved) {
        const detail = message.detail
        const uid = detail.node_id || app.runningNodeId

        if (!uid) {
            Log.log("Pepe Image Filter message has no node id")
            return
        }

        const the_node = this.find_node(uid)
        const graph_id = message.detail.graph_id

        if (detail.audiopath) this.audiopath = detail.audiopath

        // Messages from the patched backend carry the authoritative node id.
        // app.graph.id may briefly lag during frontend tab transitions.
        if (!detail.node_id && graph_id != app.graph.id) {
            this._flash_tab(graph_id)
            Log.detail(`Message for different tab`)
            return
        }

        if (!the_node) Log.log(`No node found with uid ${uid}. Maybe it's been removed. Continuing with caution`)

        if (this.node!=the_node) this.on_new_node(the_node)
        this.active_graph_id = graph_id
        this.active_request_id = detail.request_id

        if (detail.tick) {
            this.counter_text.innerText = `${detail.tick}s`
            if (this.state==State.INACTIVE) this.request_reset()
            return
        }

        if (detail.timeout) {
            this.close()
            return Log.log(`Image Filter Timeout`)
        }

        if (this.handling_message) return Log.detail(`Ignoring message because we're already handling a message`)

        this.set_title(this.node?.title ?? "Pepe Image Filter")
        this.allsame = detail.allsame || false
        this.render_tip(detail.tip || "")

        if (this.state==State.INACTIVE && app.ui.settings.getSettingValue("Pepe Image Filter.UI.Small Window") && !using_saved && !this.autosend()) {
            this.state = State.TINY
            this.saved_message = message
            this.tiny_image.src = get_full_url(message.detail.urls[message.detail.urls.length-1])
            this.maybe_play_sound()
            return `Deferring message and showing small window`
        }

        try {
            this.handling_message = true
            this.n_extras = detail.extras ? message.detail.extras.length : 0
            this.extras_row.innerHTML = ''
            for (let i=0; i<this.n_extras; i++) { create('input', 'extra', this.extras_row, {value:detail.extras[i]}) }

            this.choice_names = Array.isArray(detail.choices) ? detail.choices : []
            this.n_choices = this.choice_names.length
            this.default_choice = Number.isInteger(detail.default_choice) ? detail.default_choice : 0
            this.choices_row.replaceChildren()
            this.choice_names.forEach((label, index)=>{
                const button = create('button', 'control choice', this.choices_row, {innerText:label})
                button.title = `Choice ${index}`
                button.addEventListener('click', ()=>this.send_choice(index))
            })

            if (!using_saved && !this.autosend()) this.maybe_play_sound()

            if (detail.maskedit)   this.handle_maskedit(detail)
            else if (detail.urls)  this.handle_urls(detail)

        } finally { this.handling_message = false }
    }

    render_tip(tip) {
        this.tip_row.replaceChildren()
        for (const part of tip.split(/(\{\{.*?\}\}|\r\n|\r|\n)/gs)) {
            if (!part) continue
            if (/^(?:\r\n|\r|\n)$/.test(part)) {
                this.tip_row.append(document.createElement('br'))
            } else if (part.startsWith('{{') && part.endsWith('}}')) {
                const tag = document.createElement('span')
                tag.classList.add('insertable')
                tag.textContent = part.slice(2, -2)
                tag.addEventListener('click', ()=>{
                    this.text_edit.value += `${tag.textContent} `
                    this.text_edit.focus()
                })
                this.tip_row.append(tag)
            } else {
                this.tip_row.append(document.createTextNode(part))
            }
        }
    }

    window_not_showing(uid) {
        const node = this.find_node(uid)
        return (
            (POPUP_NODES.includes(node.type) && this.classList.contains('hidden')) ||
            (MASK_NODES.includes(node.type) && !mask_editor_showing())
        )
    }

    set_title(title) {
        this.floating_window.set_title(title)
        var pos = this.floater_position()
        if (pos) this.floating_window.move_to(pos.x, pos.y)
        pos = this.tiny_position()
        if (pos) this.tiny_window.move_to(pos.x, pos.y)
        this.tiny_window.set_title(title)
    }

    handle_maskedit(detail) {
        if ( mask_editor_showing() ) {
            return
        }
        if (!this.node) {
            Log.log(`No node to handle maskedit - maybe it's been removed`)
            this.seen_editor = true
        } else {
            this.state = State.MASK
            this.node.imgs = []
            this.node.images = []
            detail.urls.forEach((url, i)=>{
                this.node.imgs.push( new Image() );
                this.node.imgs[i].src = api.apiURL( `/view?filename=${encodeURIComponent(url.filename)}&type=${url.type}&subfolder=${url.subfolder}`)
                this.node.images.push( url )
            })
            this.node.imageIndex = 0
            open_maskeditor(this.node)
            this.seen_editor = false
        }
        setTimeout(this.wait_while_mask_editing.bind(this), 200)
    }

    wait_while_mask_editing() {
        if (!this.seen_editor && mask_editor_showing()) {
            mask_editor_listen_for_cancel( this.send_cancel.bind(this) )
            this.render()
            this.seen_editor = true
        }

        if (mask_editor_showing()) {
            setTimeout(this.wait_while_mask_editing.bind(this), 100)
        } else {
            setTimeout(this.when_mask_editor_closes.bind(this), 300) // allow a pause to make sure the mask editor has saved the image to the node
        }
    }

    when_mask_editor_closes() {
        if (this.node.imgs?.[0]?.src) {
            this._send_response({masked_image:this.extract_filename(this.node.imgs[0].src)})
        } else {
            this._send_response({masked_image:this.node.images?.[0]?.filename})
        }
        remove_preview(this.node)
    }

    extract_filename(url_string) {
        return (new URL(url_string)).searchParams.get('filename')
    }

    handle_urls(detail) {
        this.video_frames = detail.video_frames || 1
        this.equirectangular_projection = Boolean(detail.equirectangular_projection) && this.video_frames==1
        this.projected_view = {...DEFAULT_VIEW}
        this.projected_load_version += 1

        // do this after the extras are set up so that we send the right extras
        if (this.autosend()) {
            return this._send_response({selection:[0,]})
        }

        this.autozoom_pending = false
        if (detail.text != null) {
            this.state = State.TEXT
            //this.text_edit.innerHTML = detail.text
            this.text_edit.value = detail.text
            if (detail.textareaheight) this.text_edit.style.height = `${detail.textareaheight}px`
        } else {
            if (!this.equirectangular_projection && this.state != State.FILTER && this.state != State.ZOOMED && app.ui.settings.getSettingValue("Pepe Image Filter.UI.Start Zoomed")!=0) {
                this.autozoom_pending = true
            }
            this.state = State.FILTER
        }

        this.n_images = (this.video_frames<=1) ? detail.urls.length : Math.ceil(detail.urls.length / this.video_frames)
        this.laidOut = -1
        this.picked = new Set()
        if (this.n_images==1) this.picked.add('0')

        this.grid.innerHTML = ''
        this.overlaygrid.innerHTML = ''

        var latestImage
        detail.urls.forEach((url, i)=>{
            Log.log(url)
            if (i%this.video_frames == 0) {
                latestImage = create('img', null, this.grid, {src:get_full_url(url)})
                latestImage.onload = this.layout.bind(this)
                latestImage.image_index = i/this.video_frames
                latestImage.addEventListener('mouseover', this.on_mouse_enter.bind(this))
                latestImage.addEventListener('mouseout', this.on_mouse_out.bind(this))
                latestImage.frames = [get_full_url(url),]
            } else {
                latestImage.frames.push(get_full_url(url))
            }
            if (detail.mask_urls && this.video_frames==1) { create('img', null, this.overlaygrid, {src:get_full_url(detail.mask_urls[i])}) }
        })

        this.layout()

        if (this.equirectangular_projection && this.grid.firstChild) {
            this.show_projected(this.grid.firstChild)
        }

        if (this.video_frames>1) {
            this.frame = 0
            setTimeout(this.advance_videos.bind(this), 1000)
        }

        /* cooldown to prevent us catching a click that was intended for an element we are now covering */
        this.in_cooldown = true
        setTimeout(()=>{this.in_cooldown = false}, 500)

    }

    advance_videos() {
        if (this.state == State.INACTIVE) return

        this.frame = (this.frame+1)%this.video_frames
        Array.from(this.grid.children).forEach((img)=>{img.src = img.frames[this.frame]})

        const fps = app.ui.settings.getSettingValue("Pepe Image Filter.Video.FPS")
        const delay = (fps>0) ? 1000/fps : 1000
        setTimeout(this.advance_videos.bind(this), delay)
    }

    on_mouse_enter(e) {
        this.mouse_is_over = e.target
        this.redraw()
    }

    on_mouse_out(e) {
        this.mouse_is_over = null
        this.redraw()
    }

    zoom_auto() {
        this.autozoom_pending = false
        if (app.ui.settings.getSettingValue("Pepe Image Filter.UI.Start Zoomed")==1) {
            this.zoomed_image_holder = this.grid.firstChild
        } else if (app.ui.settings.getSettingValue("Pepe Image Filter.UI.Start Zoomed")==-1) {
            this.zoomed_image_holder = this.grid.lastChild
        } else {
            return
        }
        if (this.zoomed_image_holder.image_index>=0) {
            this.state = State.ZOOMED
            return this.show_zoomed()
        }
    }
    zoom_next() {
        this.zoomed_image_holder = this.zoomed_image_holder.nextSibling || this.zoomed_image_holder.parentNode.firstChild
        this.show_zoomed()
    }
    zoom_prev() {
        this.zoomed_image_holder = this.zoomed_image_holder.previousSibling || this.zoomed_image_holder.parentNode.lastChild
        this.show_zoomed()
    }
    ensure_projected_renderer() {
        if (this.projected_renderer) return true
        try {
            this.projected_renderer = new PanoramaRenderer(this.projected_canvas)
            return true
        } catch (error) {
            console.error('[Pepe Image Filter panorama]', error)
            this.equirectangular_projection = false
            this.state = State.FILTER
            this.render_projection_warning(`Panorama projection unavailable: ${String(error.message || error)}`)
            this.render()
            return false
        }
    }
    show_projected(holder) {
        if (!holder || !this.ensure_projected_renderer()) return
        this.zoomed_image_holder = holder
        this.state = State.PROJECTED
        const version = ++this.projected_load_version
        this.projected_status.innerText = 'Loading panorama…'
        const image = new Image()
        image.onload = ()=>{
            if (version!=this.projected_load_version) return
            try {
                this.projected_renderer.setImage(image)
                this.draw_projected()
            } catch (error) {
                this.projected_fallback(error)
            }
        }
        image.onerror = ()=>{
            if (version==this.projected_load_version) this.projected_fallback(new Error('Could not load panorama image'))
        }
        image.src = holder.src
        this.render()
    }
    projected_fallback(error) {
        console.error('[Pepe Image Filter panorama]', error)
        this.equirectangular_projection = false
        this.state = State.FILTER
        this.render_projection_warning('Panorama projection unavailable; using the flat grid.')
        this.render()
    }
    render_projection_warning(message) {
        this.tip_row.replaceChildren()
        const warning = document.createElement('span')
        warning.classList.add('projection_warning')
        warning.textContent = message
        this.tip_row.append(warning)
    }
    draw_projected() {
        this.projected_renderer?.render(this.projected_view)
        this.update_projected_controls()
    }
    update_projected_controls() {
        if (!this.zoomed_image_holder) return
        const index = this.zoomed_image_holder.image_index
        const selected = this.picked.has(`${index}`)
        this.projected_select_button.innerText = selected ? 'Unselect' : 'Select'
        this.projected_select_button.classList.toggle('active', selected)
        this.projected_status.innerText = `${index+1}/${this.n_images} · Yaw ${degrees(this.projected_view.yaw).toFixed(0)}° · Pitch ${degrees(this.projected_view.pitch).toFixed(0)}° · FOV ${this.projected_view.fov.toFixed(0)}°`
        this.projected_prev_button.disabled = this.n_images<2
        this.projected_next_button.disabled = this.n_images<2
        this.projected_fullscreen_button.innerText = document.fullscreenElement===this.projected ? 'Exit ⛶' : '⛶'
    }
    projected_navigate(direction) {
        if (!this.zoomed_image_holder) return
        const holder = direction>0
            ? (this.zoomed_image_holder.nextSibling || this.grid.firstChild)
            : (this.zoomed_image_holder.previousSibling || this.grid.lastChild)
        this.show_projected(holder)
    }
    toggle_projected_selection(e) {
        if (e) this.eat_event(e)
        if (!this.zoomed_image_holder) return
        this.select_unselect(this.zoomed_image_holder.image_index)
        this.render()
    }
    show_grid(e) {
        if (e) this.eat_event(e)
        if (document.fullscreenElement===this.projected) document.exitFullscreen().catch(()=>{})
        this.state = State.FILTER
        this.render()
        this.redraw()
    }
    reset_projected_view(e) {
        if (e) this.eat_event(e)
        this.projected_view = {...DEFAULT_VIEW}
        this.draw_projected()
    }
    async toggle_projected_fullscreen(e) {
        if (e) this.eat_event(e)
        try {
            if (document.fullscreenElement===this.projected) await document.exitFullscreen()
            else await this.projected.requestFullscreen()
        } catch (error) {
            this.projected_status.innerText = `Fullscreen unavailable: ${error.message}`
        }
    }
    on_projected_fullscreen_change() {
        this.update_projected_controls()
        this.draw_projected()
    }
    on_projected_pointer_down(e) {
        if (e.button!==0 || this.state!=State.PROJECTED) return
        this.projected_dragging = true
        this.projected_pointer_x = e.clientX
        this.projected_pointer_y = e.clientY
        this.projected_canvas.style.cursor = 'grabbing'
        this.projected_canvas.setPointerCapture?.(e.pointerId)
        this.eat_event(e)
    }
    on_projected_pointer_move(e) {
        if (!this.projected_dragging) return
        const sensitivity = Math.PI / Math.max(this.projected_canvas.clientHeight, 160)
        this.projected_view.yaw = normalizeYaw(this.projected_view.yaw - (e.clientX-this.projected_pointer_x)*sensitivity)
        this.projected_view.pitch = clamp(this.projected_view.pitch + (e.clientY-this.projected_pointer_y)*sensitivity, -Math.PI/2+0.01, Math.PI/2-0.01)
        this.projected_pointer_x = e.clientX
        this.projected_pointer_y = e.clientY
        this.draw_projected()
        this.eat_event(e)
    }
    on_projected_pointer_up(e) {
        if (!this.projected_dragging) return
        this.projected_dragging = false
        this.projected_canvas.style.cursor = 'grab'
        if (this.projected_canvas.hasPointerCapture?.(e.pointerId)) this.projected_canvas.releasePointerCapture(e.pointerId)
        this.eat_event(e)
    }
    on_projected_wheel(e) {
        if (this.state!=State.PROJECTED) return
        this.projected_view.fov = clamp(this.projected_view.fov + e.deltaY*0.04, MIN_FOV, MAX_FOV)
        this.draw_projected()
        this.eat_event(e)
    }
    click_zoomed() {
        const fake_event = { target:this.zoomed_image_holder}
        this.on_click(fake_event)
        this.show_zoomed()
    }
    on_zoomed_image_click(e) {
        if (this.zoom_pan_mode) {
            return this.eat_event(e)
        }
        this.click_zoomed()
    }
    show_zoomed() {
        this.reset_zoom_pan_transform()
        this.zoomed_image.src = this.zoomed_image_holder.src
        return this.render()
    }
    reset_zoom_pan_transform() {
        this.zoom_pan_scale = 1
        this.zoom_pan_x = 0
        this.zoom_pan_y = 0
        this.zoom_pan_dragging = false
        this.apply_zoom_pan_transform()
    }
    apply_zoom_pan_transform() {
        if (!this.zoomed_image) return
        this.zoomed_image.style.transform = `translate(${this.zoom_pan_x}px, ${this.zoom_pan_y}px) scale(${this.zoom_pan_scale})`
    }
    enter_zoom_pan_mode() {
        if (this.state!=State.ZOOMED) return
        this.zoom_pan_mode = true
        this.render()
    }
    exit_zoom_pan_mode() {
        this.zoom_pan_mode = false
        this.zoom_pan_dragging = false
        this.reset_zoom_pan_transform()
        this.render()
    }
    toggle_zoom_pan_mode(e) {
        if (e) this.eat_event(e)
        if (this.zoom_pan_mode) this.exit_zoom_pan_mode()
        else this.enter_zoom_pan_mode()
    }
    on_zoomed_wheel(e) {
        if (!this.zoom_pan_mode || this.state!=State.ZOOMED) return
        this.zoom_pan_scale = Math.min(8, Math.max(1, this.zoom_pan_scale * (e.deltaY < 0 ? 1.15 : 1 / 1.15)))
        if (this.zoom_pan_scale==1) {
            this.zoom_pan_x = 0
            this.zoom_pan_y = 0
        }
        this.apply_zoom_pan_transform()
        this.eat_event(e)
    }
    on_zoomed_pointer_down(e) {
        if (!this.zoom_pan_mode || this.state!=State.ZOOMED) return
        this.zoom_pan_dragging = true
        this.zoom_pan_drag_start_x = e.clientX
        this.zoom_pan_drag_start_y = e.clientY
        this.zoom_pan_start_x = this.zoom_pan_x
        this.zoom_pan_start_y = this.zoom_pan_y
        this.zoomed_image.setPointerCapture(e.pointerId)
        this.eat_event(e)
    }
    on_zoomed_pointer_move(e) {
        if (!this.zoom_pan_dragging) return
        this.zoom_pan_x = this.zoom_pan_start_x + e.clientX - this.zoom_pan_drag_start_x
        this.zoom_pan_y = this.zoom_pan_start_y + e.clientY - this.zoom_pan_drag_start_y
        this.apply_zoom_pan_transform()
        this.eat_event(e)
    }
    on_zoomed_pointer_up(e) {
        if (!this.zoom_pan_dragging) return
        this.zoom_pan_dragging = false
        if (this.zoomed_image.hasPointerCapture?.(e.pointerId)) this.zoomed_image.releasePointerCapture(e.pointerId)
        this.eat_event(e)
    }
    eat_event(e) {
        e.stopPropagation()
        e.preventDefault()
    }

    on_key_press(e) {
        if (document.activeElement?.type=='text' || document.activeElement?.type=='textarea') {
            if (this.floating_window.contains(document.activeElement) || this.contains(document.activeElement)) return
        }
        if (this.state!=State.INACTIVE && this.state!=State.TINY) {
            this.eat_event(e)
        }
    }

    on_key_down(e) {
        if (document.activeElement?.type=='text' || document.activeElement?.type=='textarea') {
            if (this.floating_window.contains(document.activeElement) || this.contains(document.activeElement)) return
            if (this.state==State.INACTIVE && this.state==State.TINY) return
        }
        if (this.state==State.FILTER || this.state==State.TEXT) {
            if (e.key=='Enter') {
                this.send_current_state()
                return this.eat_event(e)
            }
            if (e.key=='Escape') {
                this.send_cancel()
                return this.eat_event(e)
            }
            if (`${parseInt(e.key)}`==e.key) {
                this.select_unselect(parseInt(e.key))
                this.render()
                return this.eat_event(e)
            }
        }

        if (this.state==State.FILTER) {
            if (e.key==' ' && this.mouse_is_over) {
                this.eat_event(e)
                if (this.equirectangular_projection) return this.show_projected(this.mouse_is_over)
                this.state = State.ZOOMED
                this.zoomed_image_holder = this.mouse_is_over
                return this.show_zoomed()
            }
            if (e.key=='a' && e.ctrlKey) {
                if (this.picked.size>this.n_images/2) {
                    this.picked.clear()
                    console.log('unselect all')
                } else {
                    this.picked.clear()
                    for (var i=0; i<this.n_images; i++) {
                        this.picked.add(`${i}`)
                    }
                    console.log('select all')
                }
                this.eat_event(e)
                return this.redraw()
            }
        }

        if (this.state==State.ZOOMED) {
            if (this.zoom_pan_mode && e.key=='Escape') {
                this.exit_zoom_pan_mode()
                return this.eat_event(e)
            }
            if (e.key==' ') {
                this.exit_zoom_pan_mode()
                this.state = State.FILTER
                this.zoomed_image_holder = null
                this.eat_event(e)
                return this.render()
            } else if (e.key=='ArrowUp') {
                this.click_zoomed()
                return this.eat_event(e)
            } else if (e.key=='ArrowDown') {
                // select or unselect
            } else if (e.key=='ArrowRight') {
                this.zoom_next()
                return this.eat_event(e)
            } else if (e.key=='ArrowLeft') {
                this.zoom_prev()
                return this.eat_event(e)
            }
        }
        if (this.state==State.PROJECTED) {
            if (e.key=='Enter') {
                this.toggle_projected_selection(e)
            } else if (e.key=='Escape' && document.fullscreenElement!==this.projected) {
                this.show_grid(e)
            } else if (e.key=='ArrowRight') {
                this.projected_navigate(1)
                this.eat_event(e)
            } else if (e.key=='ArrowLeft') {
                this.projected_navigate(-1)
                this.eat_event(e)
            }
        }
    }

    select_unselect(n) {
        if (n<0 || n>=this.n_images) return
        const s = `${n}`

        switch (app.ui.settings.getSettingValue("Pepe Image Filter.Actions.Multiple Selection")) {
            case 1: // No - selecting sends image
                this.picked.add(s)
                this._send_response()
                break
            case 2: // No - selecting unselects previous
                this.picked.clear()
                this.picked.add(s)
                this.redraw()
                break
            case 0: // Yes - allow multiple selection
            default:
                if (this.picked.has(s)) this.picked.delete(s)
                else this.picked.add(s)
                this.redraw()
                break
        }
    }

    on_click(e) {
        if (this.in_cooldown) return;
        if (e.target.image_index != undefined) {
            this.select_unselect(e.target.image_index)
        }
    }

    layout(norepeat) {
        const box = this.grid.getBoundingClientRect()
        if (this.laidOut==box.width) return

        const im_w = this.grid.firstChild.naturalWidth
        const im_h = this.grid.firstChild.naturalHeight

        if (!im_w || !im_h || !box.width || !box.height) {
            if (!norepeat) setTimeout(this.layout.bind(this), 100, [true,])
            return
        } else {
            var best_scale = 0
            var best_pick
            var per_row
            for (per_row=1; per_row<=this.n_images; per_row++) {
                const rows = Math.ceil(this.n_images/per_row)
                const scale = Math.min( box.width/(im_w*per_row), box.height/(im_h*rows) )
                if (scale>best_scale) {
                    best_scale = scale
                    best_pick = per_row
                }
            }
            this.per_row = best_pick
            this.laidOut = box.width
        }

        this.rows = Math.ceil(this.n_images/this.per_row)
        const w = (box.width / this.per_row)-GRID_IMAGE_SPACE
        const h = (box.height / this.rows)-GRID_IMAGE_SPACE

        var template_columns = ''
        for (let i=0; i<this.per_row; i++) template_columns += ` ${w+GRID_IMAGE_SPACE}px`
        var template_rows = ''
        for (let i=0; i<this.rows; i++) template_rows += ` ${h+GRID_IMAGE_SPACE}px`
        this.grid.style.gridTemplateColumns = template_columns
        this.grid.style.gridTemplateRows = template_rows
        this.overlaygrid.style.gridTemplateColumns = template_columns
        this.overlaygrid.style.gridTemplateRows = template_rows

        Array.from(this.grid.children).forEach((c,i)=>{
            c.style.gridArea = `${Math.floor(i/this.per_row) + 1} / ${i%this.per_row + 1} /  auto / auto`;
        })
        Array.from(this.overlaygrid.children).forEach((c,i)=>{
            c.style.gridArea = `${Math.floor(i/this.per_row) + 1} / ${i%this.per_row + 1} /  auto / auto`;
        })

        this.redraw()
        setTimeout(this.rescale_images.bind(this), 100)

        if (this.autozoom_pending) {
            this.zoom_auto()
        }
    }

    rescale_images() {
        const box = this.grid.getBoundingClientRect()
        const sub = this.grid.firstChild.getBoundingClientRect()
        const w_used = (sub.width+GRID_IMAGE_SPACE)*this.per_row / box.width
        const h_used = (sub.height+GRID_IMAGE_SPACE)*this.rows / box.height
        const could_zoom = 1.0 / Math.max(w_used, h_used)
        if (could_zoom>1 && app.ui.settings.getSettingValue("Pepe Image Filter.UI.Enlarge Small Images")) {
            Array.from(this.grid.children).forEach((img)=>{
                img.style.width = `${sub.width*could_zoom}px`
            })
            Array.from(this.overlaygrid.children).forEach((img)=>{
                img.style.width = `${sub.width*could_zoom}px`
            })
        }

    }

    redraw() {
        Array.from(this.grid.children).forEach((c,i)=>{
            if (this.picked.has(`${i}`)) c.classList.add('selected')
            else c.classList.remove('selected')

            if (c == this.mouse_is_over) c.classList.add('hover')
            else c.classList.remove('hover')
        })
    }

}

customElements.define('pepe-image-filter-popup', Popup)

export const popup = new Popup()

export function remove_preview(node, previous_tries=0, delay=50) {
    const w = node?.widgets?.find((w)=>{return w.name=='$$canvas-image-preview'})
    if (w && !w.hidden) {
        w.hidden = true
        node.setSize( [node.size[0], node.computeSize()[1]] )
        app.canvas.setDirty(true,true)
        console.log(`Removed preview from node ${node.id} after ${previous_tries} tries`)
    } else {
        if (previous_tries<6) setTimeout(remove_preview, delay, node, previous_tries+1, delay*2)
    }
}
