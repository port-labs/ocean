import React, {useEffect, useState} from 'react';
import XMLParser from 'react-xml-parser';


import './custom.css';

const BUCKET_URL = "https://port-graphical-assets.s3.eu-west-1.amazonaws.com";

function Icon(props): JSX.Element {
    const {iconName} = props;
    const [Icon, setIcon] = useState(null);

    useEffect(async () => {
        for (const folder of ["blueprintsColor", "blueprints"]) {
            try {
                const seachParams = new URLSearchParams({
                    "list-type": '2',
                    prefix: `icons/${folder}`
                })
                const response = await fetch(`${BUCKET_URL}?` + seachParams)
                const r = await response.text()
                const xml = new XMLParser().parseFromString(r);
                const iconInS3 = xml.children.filter((child) => child.name === "Contents").map((content) => {
                    const key = content.children.find((child) => child.name === "Key").value;
                    const name = key.split("/").pop().split(".")[0];
                    return [name, key]
                }).find(([name, key]) => name.toLowerCase() === iconName.toLowerCase());

                if (iconInS3) {
                    const svgResponse = await fetch(`${BUCKET_URL}/${iconInS3[1]}`)
                    const text = await svgResponse.text();
                    setIcon(text);
                    return;
                }
            } catch (error) {
            }
        }
    }, [iconName]);

    return (
        <div className={"svg-container"} style={{
            backgroundColor: 'white',
            borderRadius: "50%",
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: "1px solid #dddddd"
        }}>
            <div style={{width: '80%', height: '80%'}} dangerouslySetInnerHTML={{__html: Icon}}/>
        </div>
    );
}

export default Icon;
