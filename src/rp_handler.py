"""
The main serverless worker module for runpod
"""

# system lib imports
import json
import os

# required lib imports
import runpod

# src imports
import comftroller
import uploader
import utils 

# additional outputs logging. helpful for testing 
LOG_JOB_OUTPUTS = True
env = os.environ.get('ENV', 'production')

utils.log(f"ENV: {env}")

def handler(job):
    """
    The main function that handles a job of generating an image.

    This function validates the input, sends a prompt to ComfyUI for processing,
    polls ComfyUI for result, and retrieves generated images.

    Args:
        job (dict): A dictionary containing job details and input parameters.

    Returns:
        dict: A dictionary containing either an error message or a success status with generated images.
    """
    job_input = job["input"]  # input workflow

    # Validate inputs
    if job_input is None:
        return utils.error(f"no 'input' property found on job data")

    if job_input.get("workflow") is None:
        return utils.error(f"no 'workflow' property found on job data")
    
    # if workflow is a string then validate will try convert to json
    workflow = utils.validate_json(job_input.get("workflow"))
    # ensure workflow is valid JSON:
    if workflow is None:
        return utils.error(f"'workflow' must be a valid JSON object or JSON-encoded string")

    bucket_creds = None # default, since we want to use ENV variable instead (if set) :)

    # validate that we can use 'aws' property 
    custom_aws = utils.validate_json(job_input.get("tobucket"))
    if custom_aws is not None:
        utils.log(f"will attempt to use 'tobucket' credentials from job input for aws upload")
        bucket_creds = custom_aws # set bucket creds for uploader
        custom_aws = None # no need to store any longer

    # get ENV variable for aws creds if not set in job input

    # set callback for when comftroller processes incomming data

    if(env == 'production'):
        update_progress = lambda data: runpod.serverless.progress_update(job, data)
    else:
        update_progress = utils.log

    input_files = job_input.get("files", [])

    # outputs is equal to the completed comfyui job id history object
    outputs = comftroller.run(workflow, input_files, update_progress)
    # if LOG_JOB_OUTPUTS:
    #     utils.log("---- RAW OUTPUTS ----")
    #     utils.log(outputs)
    #     utils.log("")

    # if 'run' had an error, then stop job and return error as result
    if outputs.get('error'):
        return outputs.get('error')

    # Fetching generated images
    output_files = [] # array of output filepath/urls
    output_datas = {} # dict of nont image output node datas as {"nodeid":{"outputdata":...}}

    # uglry nesterd lewpz: el boo!
    for node_id, node_output in outputs.items():
        # add output data to output_datas if not images or gifs data
        # scan job outputs for images/gifs (videos)
        if "images" in node_output:
            for data in node_output["images"]:
                output_datas[node_id] = node_output
                if data.get("type") == 'output':
                    if(data['subfolder'] == ''):
                        path = f"{data['filename']}"
                    else:    
                        path = f"{data['subfolder']}/{data['filename']}"
                    output_files.append(path)

    # if you dont know what this does... you shouldnt be here.
    utils.log(f"#files generated: {len(output_files)}")
    if LOG_JOB_OUTPUTS:
        utils.log("---- OUTPUT DATAS ----")
        utils.log(output_datas)
        utils.log("")

    # return an error if for some reason the files cant be found. 
    # should never happen... but just in case <3
    # for outfile in output_files:
    #     if not os.path.exists(outfile):
    #         return utils.error(f"couldn't locate output file: {outfile} #sadface")

    # log progress update to runpod so it knows we might take a moment to upload to aws
    update_progress({"saving-image-data": True})

    base = comftroller.GENERATION_OUTPUT_PATH
    # attempt to upload the generated files to aws, 
    # send_to_aws returns (True, [file urls, ...]) or (False, [file paths, ...])
    aws_uploaded, bucket_urls = uploader.send_to_aws(base, output_files, 'outputs', bucket_creds)

    # define return object 
    job_result = {}
    job_result["files"] = bucket_urls
    job_result["datas"] = output_datas

    # convert generated image to base64 if not uploaded to aws and able
    # !NOTE: RUNPOD HAS PAYLOAD LIMITS!! CANNOT RETURN BASE64 FOR MULTIPLE LARGE FILES!!!
    if not aws_uploaded and utils.job_prop_to_bool(job_input, "tobase64"):
        for index, local_file in enumerate(bucket_urls):
            job_result["files"][index] = utils.base64_encode(local_file)

    return job_result


# Start the handler
runpod.serverless.start({"handler": handler})
