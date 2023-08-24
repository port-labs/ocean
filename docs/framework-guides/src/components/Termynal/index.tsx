import {useEffect, useRef, useState} from "react";

interface Props {
    prefix: String,
    startDelay: Number,
    typeDelay: Number,
    lineDelay: Number,
    progressLength: Number,
    progressChar: String,
    progressPercent: Number,
    cursor: String,
    lineData: Array,
    noInit: Boolean,
    children: HTMLLIElement,
}

interface ComponentState {
    pfx: String,
    startDelay: Number,
    typeDelay: Number,
    lineDelay: Number,
    originalStartDelay: Number,
    originalTypeDelay: Number,
    originalLineDelay: Number,
    progressLength: Number,
    progressChar: String,
    progressPercent: Number,
    cursor: String,
    lineData: Array,
    lineHtml: Array,
}

export default function Index(props: Props) {
    const r = useRef(null)
    const [container, setContainer] = useState<HTMLLIElement | null>(null)
    const [state, setState] = useState<ComponentState>(null)
    const [linesState, setLineState] = useState([])

    useEffect(() => {
        createTermynal()
        loadVisibleTermynals();
        window.addEventListener("scroll", loadVisibleTermynals);
    }, [])


    useEffect(() => {
        if (container == null) return;

        const pfx = `data-${props.prefix || 'ty'}`;
        const startDelay = props.startDelay
            || parseFloat(container.getAttribute(`${pfx}-startDelay`)) || 600;
        const originalStartDelay = startDelay;
        const typeDelay = props.typeDelay
            || parseFloat(container.getAttribute(`${pfx}-typeDelay`)) || 90;
        const originalTypeDelay = typeDelay
        const lineDelay = props.lineDelay
            || parseFloat(container.getAttribute(`${pfx}-lineDelay`)) || 1500;
        const originalLineDelay = lineDelay;
        const progressLength = props.progressLength
            || parseFloat(container.getAttribute(`${pfx}-progressLength`)) || 40;
        const progressChar = props.progressChar
            || container.getAttribute(`${pfx}-progressChar`) || '█';
        const progressPercent = props.progressPercent
            || parseFloat(container.getAttribute(`${pfx}-progressPercent`)) || 100;
        const cursor = props.cursor
            || container.getAttribute(`${pfx}-cursor`) || '▋';
        const lineData = props.lineData;

        setState({
            pfx,
            startDelay,
            typeDelay,
            lineDelay,
            originalStartDelay,
            originalTypeDelay,
            originalLineDelay,
            progressLength,
            progressChar,
            progressPercent,
            cursor,
            lineData,
            lineHtml: []
        })


        if (!props.noInit) init()
    }, [container])

    useEffect(() => {
        if (container == null || state == null || state.lineData == null) return;
        const s = {
            ...state,
            lineHtml: lineDataToElements(state.lineData)
        }
        setState(s)
        loadLines(s)
    }, [state, container])

    function createTermynal() {
        const progressLiteralStart = "---> 100%";
        const promptLiteralStart = "$ ";
        const customPromptLiteralStart = "# ";

        const text = r.current.children[0].children[0].children[0].textContent;
        const lines = text.split("\n");
        const useLines = [];
        let buffer = [];

        function saveBuffer() {
            if (buffer.length) {
                let isBlankSpace = true;
                buffer.forEach(line => {
                    if (line) {
                        isBlankSpace = false;
                    }
                });
                const dataValue = {};
                if (isBlankSpace) {
                    dataValue["delay"] = 0;
                }
                if (buffer[buffer.length - 1] === "") {
                    // A last single <br> won't have effect
                    // so put an additional one
                    buffer.push("");
                }
                const bufferValue = buffer.join("<br>");
                dataValue["value"] = bufferValue;
                useLines.push(dataValue);
                buffer = [];
            }
        }

        for (let line of lines) {
            if (line === progressLiteralStart) {
                saveBuffer();
                useLines.push({
                    type: "progress"
                });
            } else if (line.startsWith(promptLiteralStart)) {
                saveBuffer();
                const value = line.replace(promptLiteralStart, "").trimEnd();
                useLines.push({
                    type: "input",
                    value: value
                });
            } else if (line.startsWith("// ")) {
                saveBuffer();
                const value = "? " + line.replace("// ", "").trimEnd();
                useLines.push({
                    value: value,
                    class: "termynal-comment",
                    delay: 0
                });
            } else if (line.startsWith(customPromptLiteralStart)) {
                saveBuffer();
                const promptStart = line.indexOf(promptLiteralStart);
                if (promptStart === -1) {
                    console.error("Custom prompt found but no end delimiter", line)
                }
                const prompt = line.slice(0, promptStart).replace(customPromptLiteralStart, "")
                let value = line.slice(promptStart + promptLiteralStart.length);
                useLines.push({
                    type: "input",
                    value: value,
                    prompt: prompt
                });
            } else {
                buffer.push(line);
            }
        }

        saveBuffer();
        const div = document.createElement("div");
        setState({
            ...state,
            lineData: useLines,
            lineDelay: 500
        })

        r.current.replaceWith(div);
        setContainer(div)
        console.log(div);

    }

    function loadVisibleTermynals() {
        if (container && container.getBoundingClientRect().top - innerHeight <= 0) {
            init();
            return false;
        }
        return true;
    }

    function loadLines(s) {
        const topEl = document.createElement('a')
        topEl.style.visibility = 'hidden'
        container.appendChild(topEl)
        // Appends dynamically loaded lines to existing line elements.
        const x = [...container.querySelectorAll(`[${state.pfx}]`)].concat(s.lineHtml)

        setLineState(s.lineData);
        for (let line of x) {
            line.style.visibility = 'hidden'
            container.appendChild(line)
        }
        container.setAttribute('data-termynal', '');
    }

    function _attributes(line) {
        let attrs = '';
        for (let prop in line) {
            // Custom add class
            if (prop === 'class') {
                attrs += ` class=${line[prop]} `
                continue
            }
            if (prop === 'type') {
                attrs += `${state.pfx}="${line[prop]}" `
            } else if (prop !== 'value') {
                attrs += `${state.pfx}-${prop}="${line[prop]}" `
            }
        }

        return attrs;
    }

    function lineDataToElements(lineData) {
        return lineData.map(line => {
            let div = document.createElement('div');
            div.innerHTML = `<span ${_attributes(line)}>${line.value || ''}</span>`;

            return div.firstElementChild;
        });
    }

    function _wait(time) {
        return new Promise(resolve => setTimeout(resolve, time));
    }

    async function progress(line) {
        const progressLength = line.getAttribute(`${state.pfx}-progressLength`)
            || state.progressLength;
        const progressChar = line.getAttribute(`${state.pfx}-progressChar`)
            || state.progressChar;
        const chars = progressChar.repeat(progressLength);
        const progressPercent = line.getAttribute(`${state.pfx}-progressPercent`)
            || state.progressPercent;
        line.textContent = '';
        container.appendChild(line);

        for (let i = 1; i < chars.length + 1; i++) {
            await _wait(state.typeDelay);
            const percent = Math.round(i / chars.length * 100);
            line.textContent = `${chars.slice(0, i)} ${percent}%`;
            if (percent > progressPercent) {
                break;
            }
        }
    }

    async function type(line) {
        const chars = [...line.textContent];
        line.textContent = '';
        container.appendChild(line);

        for (let char of chars) {
            const delay = line.getAttribute(`${state.pfx}-typeDelay`) || state.typeDelay;
            await _wait(delay);
            line.textContent += char;
        }
    }

    function generateRestart(topEl) {
        topEl.onclick = (e) => {
            e.preventDefault()
            container.innerHTML = ''
            init()
        }

        topEl.innerHTML = "restart ↻"
    }

    function generateFinish(topEl) {
        topEl.onclick = (e) => {
            e.preventDefault()
            setState({
                ...state,
                startDelay: 0,
                typeDelay: 0,
                lineDelay: 0,
            })
        }

        topEl.innerHTML = "fast →"
        return topEl
    }

    async function start() {
        const topElement = document.createElement('a')
        topElement.href = '#'
        topElement.setAttribute('data-terminal-control', '')
        generateFinish(topElement)
        container.appendChild(topElement)
        await _wait(state.startDelay);
        for (let line of linesState) {
            const type = line.getAttribute(state.pfx);
            const delay = line.getAttribute(`${state.pfx}-delay`) || state.lineDelay;

            if (type == 'input') {
                line.setAttribute(`${state.pfx}-cursor`, state.cursor);
                await type(line);
                await _wait(delay);
            } else if (type == 'progress') {
                await progress(line);
                await _wait(delay);
            } else {
                container.appendChild(line);
                await _wait(delay);
            }

            line.removeAttribute(`${state.pfx}-cursor`);
        }
        generateRestart(topElement)

        setState({
            ...state,
            lineDelay: state.originalLineDelay,
            typeDelay: state.originalTypeDelay,
            startDelay: state.originalStartDelay,
        })
    }

    function init() {
        /**
         * Calculates width and height of Termynal container.
         * If container is empty and lines are dynamically loaded, defaults to browser `auto` or CSS.
         */

        const containerStyle = getComputedStyle(r.current);
        container.style.width = containerStyle.width !== '0px' ?
            containerStyle.width : undefined;
        container.style.minHeight = containerStyle.height !== '0px' ?
            containerStyle.height : undefined;

        container.setAttribute('data-termynal', '');
        container.innerHTML = '';
        for (let line of linesState) {
            line.style.visibility = 'visible'
        }
        start().then(() => {
        });
    }

    return (
        <div>
            <div ref={r}>
                {props.children}
            </div>
        </div>
    );
}