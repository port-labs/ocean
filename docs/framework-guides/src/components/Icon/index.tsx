import React, {useEffect, useState} from 'react';

import './custom.css';

function Icon(props): JSX.Element {
    const {iconName} = props;
    const [Icon, setIcon] = useState(null);

    useEffect(async () => {
        for (const folder of ["blueprints", "blueprintsColor"]) {
            try {
                const resposne = await fetch(`https://port-graphical-assets.s3.eu-west-1.amazonaws.com/icons/${folder}/${iconName}.svg`)
                if (resposne.status === 200) {
                    const text = await resposne.text();
                    console.log(text);
                    setIcon(<div className={"svg-container"} dangerouslySetInnerHTML={{__html: text}}/>);
                }
            } catch (error) {
            }

            if (Icon) {
                return;
            }
        }
    }, [iconName]);

    return Icon;
}

export default Icon;
