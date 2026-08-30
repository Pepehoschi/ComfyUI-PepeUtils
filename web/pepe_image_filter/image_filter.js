import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

import { create } from "./utils.js";
import { popup } from "./popup.js";
import { graph_id_to_tab } from "./graph_map.js";
import { Log } from "./log.js";

const FILTER_TYPES = ["PepeImageFilter"]

const VERSION = "1.9"

app.registerExtension({
    name: "pepe.image_filter",
    settings: [
        {
            id: "Pepe Image Filter.About",
            name: `Pepe Image Filter (based on cg-image-filter ${VERSION})`,
            type: () => {
                const x = document.createElement('span')
                const a = document.createElement('a')
                a.innerText = "Report issues or request features"
                a.href = "https://github.com/chrisgoringe/cg-image-filter/issues"
                a.target = "_blank"
                a.style.paddingRight = "12px"
                x.appendChild(a)
                return x
            },
        },
        {
            id: "Pepe Image Filter.UI.Play Sound",
            name: "Play sound when activating",
            type: "boolean",
            defaultValue: true
        },
        {
            id: "Pepe Image Filter.UI.Enlarge Small Images",
            name: "Enlarge small images in grid",
            type: "boolean",
            defaultValue: true
        },
        {
            id: "Pepe Image Filter.Actions.Multiple Selection",
            name: "Allow multiple images to be selected",
            type: "combo",
            options: [ {value:0, text:"Yes"}, {value:1, text:"No - selecting sends image"}, {value:2, text:"No - selecting unselects previous"} ],
            default: 0,
        },
        {
            id: "Pepe Image Filter.Actions.Autosend Identical",
            name: "If all images are identical, autosend one",
            type: "boolean",
            defaultValue: false
        },
        {
            id: "Pepe Image Filter.UI.Start Zoomed",
            name: "Enter Pepe Image Filter with an image zoomed",
            type: "combo",
            options: [ {value:0, text:"No"}, {value:"1", text:"first"}, {value:"-1", text:"last"} ],
            default: 0,
        },
        {
            id: "Pepe Image Filter.UI.Small Window",
            name: "Show a small popup instead of covering the screen",
            type: "boolean",
            tooltip: "Click the small popup to activate it",
            defaultValue: false
        },
        {
            id: "Pepe Image Filter.Z.Detailed Logging",
            name: "Turn on detailed logging",
            tooltip: "If you are asked to for debugging!",
            type: "boolean",
            defaultValue: false
        },
        {
            id: "Pepe Image Filter.Video.FPS",
            name: "Video Frames per Second",
            type: "int",
            defaultValue: 5,
        }
    ],
    setup() {
        create('link', null, document.getElementsByTagName('HEAD')[0],
            {'rel':'stylesheet', 'type':'text/css', 'href': new URL("./filter.css", import.meta.url).href } )
        create('link', null, document.getElementsByTagName('HEAD')[0],
            {'rel':'stylesheet', 'type':'text/css', 'href': new URL("./floating_window.css", import.meta.url).href } )
        create('link', null, document.getElementsByTagName('HEAD')[0],
            {'rel':'stylesheet', 'type':'text/css', 'href': new URL("./zoomed.css", import.meta.url).href } )
        api.addEventListener("execution_interrupted", popup.send_cancel.bind(popup));
        api.addEventListener("pepe-image-filter-images", popup.handle_message.bind(popup));
    },
    async beforeRegisterNodeDef(nodeType) {
        if (FILTER_TYPES.includes(nodeType.comfyClass )) {
        /*
            When a node gets configured, set the graph widget.
            The base configure method sets widgets and other stuff, so call that *first*
        */
            const configure = nodeType.prototype.configure;
            nodeType.prototype.configure = function () {
                configure?.apply(this, arguments)
                set_graph_id_widget(this)
            }
            const onNodeCreated = nodeType.prototype.onNodeCreated;
        /*
            Similarly, when a node is created.
        */
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                set_graph_id_widget(this)
                return r
            }
        }
    },

    afterConfigureGraph() { link_to_tab(3) }
})

function set_graph_id_widget(node) {
    const graph_id_widget = node.widgets?.find((n)=>n.name=='graph_id')
    if (graph_id_widget) {
        graph_id_widget.hidden = true
        graph_id_widget.value = `${app.graph.id}`
        graph_id_widget.computeSize = () => [0,0]
    }
}

function link_to_tab(tries) {
    const tab = document.getElementsByClassName('p-togglebutton-checked')[0]
    if (tab && app.graph.id) {
        graph_id_to_tab.set(app.graph.id, tab )
    } else if (tries>0) {
        setTimeout( ()=> { link_to_tab(tries-1) }, 500 )
    } else {
        Log.log(`Pepe Image Filter: could not link graph to tab`)
    }
}
